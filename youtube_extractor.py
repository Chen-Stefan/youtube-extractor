import os
import re
import tempfile
from typing import Optional, Dict, Any, Tuple
import subprocess
import json
import requests
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled

class YouTubeExtractor:
    def __init__(self, video_url: str):
        self.video_url = video_url
        self.video_id = self.extract_video_id(video_url)
        self.transcript = None
        
    def extract_video_id(self, url: str) -> str:
        """从YouTube URL中提取视频ID"""
        patterns = [
            r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
            r'youtu.be/([0-9A-Za-z_-]{11})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        raise ValueError("无法从URL中提取视频ID")

    def get_available_transcript_languages(self) -> list:
        """获取可用的字幕语言列表"""
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(self.video_id)
            languages = []
            for transcript in transcript_list:
                languages.append({
                    'language_code': transcript.language_code,
                    'language': transcript.language,
                    'is_generated': transcript.is_generated
                })
            return languages
        except Exception as e:
            print(f"获取字幕语言列表时出错: {str(e)}")
            return []

    def get_transcript(self, language: Optional[str] = None) -> Tuple[str, bool]:
        """尝试获取字幕，返回字幕内容和是否成功获取"""
        try:
            if language:
                transcript_list = YouTubeTranscriptApi.get_transcript(self.video_id, languages=[language])
            else:
                # 尝试获取所有可用字幕中的一个
                transcript_list = YouTubeTranscriptApi.get_transcript(self.video_id)
            
            # 将字幕列表转换为纯文本
            full_text = ' '.join([entry['text'] for entry in transcript_list])
            self.transcript = full_text
            return full_text, True
        except (TranscriptsDisabled, Exception) as e:
            print(f"获取字幕时出错: {str(e)}")
            return "", False

    def download_audio_and_transcribe(self, output_dir: Optional[str] = None) -> str:
        """下载视频的音频并使用Whisper进行转录"""
        try:
            # 创建临时目录或使用指定目录
            if output_dir is None:
                temp_dir = tempfile.mkdtemp()
                output_dir = temp_dir
            else:
                os.makedirs(output_dir, exist_ok=True)

            audio_path = os.path.join(output_dir, f"{self.video_id}.mp3")
            
            # 使用yt-dlp下载音频
            print(f"正在下载视频音频: {self.video_url}")
            yt_dlp_command = [
                "yt-dlp", 
                "-x", 
                "--audio-format", "mp3", 
                "--audio-quality", "0",
                "-o", audio_path,
                self.video_url
            ]
            subprocess.run(yt_dlp_command, check=True)

            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"下载失败: {audio_path}")
            
            # 使用Whisper进行转录
            print("正在使用Whisper转录音频...")
            transcript_path = os.path.join(output_dir, f"{self.video_id}.txt")
            
            # 使用Whisper命令行工具 (需要先安装whisper)
            whisper_command = [
                "whisper", 
                audio_path, 
                "--model", "medium",  # 使用最小的模型以节省资源，可选择 tiny, base, small, medium, large
                "--language", "auto",  # 自动检测语言
                "--output_dir", output_dir,
                "--output_format", "txt"
            ]
            subprocess.run(whisper_command, check=True)
            
            # 读取转录文本
            transcript_path = os.path.join(output_dir, f"{self.video_id}.txt")
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript_text = f.read()
            
            self.transcript = transcript_text
            return transcript_text
            
        except Exception as e:
            print(f"下载和转录过程中出错: {str(e)}")
            return ""

    def analyze_with_local_llm(self, prompt: str) -> str:
        """使用本地LLM分析字幕内容（示例使用ollama）"""
        if not self.transcript:
            raise ValueError("请先获取字幕内容")
        
        try:
            # 使用ollama API（假设在本地运行）
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3",  # 或其他已下载的模型
                    "prompt": f"以下是YouTube视频的字幕内容：\n\n{self.transcript}\n\n{prompt}",
                    "stream": False
                }
            )
            
            if response.status_code == 200:
                return response.json()["response"]
            else:
                return f"分析失败: {response.status_code} - {response.text}"
        
        except Exception as e:
            print(f"使用本地LLM分析时出错: {str(e)}")
            return f"分析过程中出错: {str(e)}"

    def analyze_with_claude_basic(self, api_key: str, prompt: str) -> str:
        """使用Claude API分析字幕内容，使用最经济的方式"""
        if not self.transcript:
            raise ValueError("请先获取字幕内容")

        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        # 使用更小、更经济的模型
        data = {
            "model": "claude-3-haiku-20240307",  # 使用Haiku模型降低成本
            "messages": [
                {
                    "role": "user",
                    "content": f"以下是YouTube视频的字幕内容：\n\n{self.transcript}\n\n{prompt}"
                }
            ],
            "max_tokens": 500,  # 限制输出令牌数以控制成本
            "temperature": 0.3  # 较低的温度以获得更确定的回答
        }

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            return response.json()['content'][0]['text']
        else:
            raise Exception(f"API调用失败: {response.status_code} - {response.text}")

def process_youtube_video(video_url: str, analysis_prompt: str = "总结这个视频的主要内容") -> Dict[str, Any]:
    """处理YouTube视频的完整流程，优先使用字幕，失败则下载并转录"""
    extractor = YouTubeExtractor(video_url)
    
    # 步骤1: 尝试获取现有字幕
    print("步骤1: 尝试获取现有字幕...")
    available_languages = extractor.get_available_transcript_languages()
    
    if available_languages:
        # 优先尝试中文字幕
        chinese_subs = [lang for lang in available_languages if lang['language_code'].startswith('zh')]
        if chinese_subs:
            transcript, success = extractor.get_transcript(language=chinese_subs[0]['language_code'])
        else:
            # 否则使用第一个可用字幕
            transcript, success = extractor.get_transcript(language=available_languages[0]['language_code'])
    else:
        transcript, success = "", False
    
    # 步骤2: 如果字幕获取失败，则下载并转录
    if not success or not transcript:
        print("步骤2: 字幕获取失败，尝试下载并转录...")
        transcript = extractor.download_audio_and_transcribe()
    
    # 步骤3: 分析内容
    analysis_result = "未进行分析"
    if transcript:
        print("步骤3: 分析内容...")
        try:
            # 优先使用本地LLM（如果可用）
            analysis_result = extractor.analyze_with_local_llm(analysis_prompt)
        except Exception as e:
            print(f"本地分析失败，错误: {str(e)}")
            print("如果需要使用Claude API，请提供API密钥")
    
    return {
        "video_id": extractor.video_id,
        "available_languages": available_languages,
        "transcript": transcript,
        "analysis": analysis_result
    }

# 使用示例
if __name__ == "__main__":
    video_url = "https://www.youtube.com/watch?v=3MjS9w60MMw"
    result = process_youtube_video(
        video_url, 
        "请列出这个视频中提到的华人移民需要注意的7件事。"
    )
    
    print("\n=== 处理结果 ===")
    print(f"视频ID: {result['video_id']}")
    print(f"可用字幕语言: {result['available_languages']}")
    print(f"字幕内容预览: {result['transcript'][:200]}...")
    print(f"分析结果: {result['analysis']}")