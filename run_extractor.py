from youtube_extractor import process_youtube_video
import json
import os

def main():
    # 配置输出目录
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    # 获取用户输入
    print("=== YouTube内容提取与分析工具 ===")
    video_url = input("请输入YouTube视频URL: ")
    analysis_prompt = input("请输入分析提示（直接按回车使用默认提示）: ")
    
    # 使用默认提示如果用户没有输入
    if not analysis_prompt:
        analysis_prompt = "总结这个视频的主要内容"
    
    print("\n开始处理视频...\n")
    
    # 处理视频
    result = process_youtube_video(video_url, analysis_prompt)
    
    # 保存结果
    video_id = result["video_id"]
    
    # 保存字幕
    transcript_path = os.path.join(output_dir, f"{video_id}_transcript.txt")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(result["transcript"])
    
    # 保存分析结果
    analysis_path = os.path.join(output_dir, f"{video_id}_analysis.txt")
    with open(analysis_path, "w", encoding="utf-8") as f:
        f.write(result["analysis"])
    
    # 显示结果
    print("\n=== 处理完成 ===")
    print(f"视频ID: {result['video_id']}")
    print(f"可用字幕语言: {result['available_languages']}")
    print(f"字幕已保存至: {transcript_path}")
    print(f"分析结果已保存至: {analysis_path}")
    print("\n分析结果预览:")
    print("-" * 50)
    print(result["analysis"])
    print("-" * 50)
    
    print("\n按回车键退出...")
    input()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n处理过程中出错: {str(e)}")
        print("\n按回车键退出...")
        input()