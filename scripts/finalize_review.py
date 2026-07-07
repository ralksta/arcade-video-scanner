#!/usr/bin/env python3
"""
scripts/finalize_review.py - CLI tool to manage video reviews.

This tool looks for pairs of videos in the review directory (Status="REVIEW")
and allows the user to keep the optimized version or revert to the original.
"""

import os
import sys
import shutil
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from arcade_scanner.config import config
from arcade_scanner.database import db
from arcade_scanner.models.video_entry import VideoEntry

def print_banner():
    print("╔════════════════════════════════════════╗")
    print("║   Arcade Media: Review Finalizer       ║")
    print("╚════════════════════════════════════════╝")

def get_review_pairs():
    """Find all videos with Status='REVIEW' and pair them up."""
    all_videos = db.get_all()
    review_videos = [v for v in all_videos if v.status == "REVIEW"]
    
    # Map by directory (job folder)
    jobs = {}
    for v in review_videos:
        job_dir = os.path.dirname(v.file_path)
        if job_dir not in jobs:
            jobs[job_dir] = {"original": None, "optimized": None}
        
        name = os.path.basename(v.file_path)
        if "_original" in name:
            jobs[job_dir]["original"] = v
        elif "_optimized" in name:
            jobs[job_dir]["optimized"] = v
            
    # Filter out incomplete pairs
    pairs = []
    for job_dir, data in jobs.items():
        if data["original"] and data["optimized"]:
            pairs.append(data)
    
    return pairs

def finalize_pair(pair, decision):
    """
    Apply the decision to a video pair.
    decision: 'optimized' | 'original' | 'skip'
    """
    v_orig = pair["original"]
    v_opt = pair["optimized"]
    
    final_dest = v_orig.original_path
    
    if not final_dest:
        print(f"❌ Error: Original path missing for {os.path.basename(v_orig.file_path)}")
        return False

    job_dir = os.path.dirname(v_orig.file_path)

    if decision == "optimized":
        print(f"🚀 Keeping Optimized: {os.path.basename(final_dest)}")
        # 1. Move optimized file to destination
        os.makedirs(os.path.dirname(final_dest), exist_ok=True)
        shutil.move(v_opt.file_path, final_dest)
        
        # 2. Update DB: Use optimized metadata but restore original path
        opt_dict = v_opt.model_dump(by_alias=True)
        db.remove(v_opt.file_path)
        db.remove(v_orig.file_path)
        
        opt_dict["FilePath"] = final_dest
        opt_dict["Status"] = "OK"
        opt_dict["OriginalPath"] = None
        db.upsert(VideoEntry(**opt_dict))
        
    elif decision == "original":
        print(f"⏪ Reverting to Original: {os.path.basename(final_dest)}")
        # 1. Move original file back
        os.makedirs(os.path.dirname(final_dest), exist_ok=True)
        shutil.move(v_orig.file_path, final_dest)
        
        # 2. Update DB: Restore original entry
        orig_dict = v_orig.model_dump(by_alias=True)
        db.remove(v_opt.file_path)
        db.remove(v_orig.file_path)
        
        orig_dict["FilePath"] = final_dest
        orig_dict["Status"] = "OK"
        orig_dict["OriginalPath"] = None
        db.upsert(VideoEntry(**orig_dict))
        
    # Cleanup job dir if empty or done
    try:
        if os.path.exists(job_dir):
            # Remove remaining files in job dir (like thumbnails if generated)
            for f in os.listdir(job_dir):
                f_path = os.path.join(job_dir, f)
                if os.path.isfile(f_path): os.remove(f_path)
            os.rmdir(job_dir)
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")

    return True

def main():
    print_banner()
    
    if not config.settings.enable_review_mode:
        print("ℹ️ Review Mode is currently disabled in settings.")
        # But we still continue in case there are old items to process
    
    pairs = get_review_pairs()
    
    if not pairs:
        print("✅ No pending reviews found.")
        return

    print(f"Found {len(pairs)} jobs for review.\n")
    
    for i, pair in enumerate(pairs):
        v_orig = pair["original"]
        v_opt = pair["optimized"]
        
        rel_path = os.path.basename(v_orig.original_path or v_orig.file_path)
        print(f"--- Job {i+1}/{len(pairs)}: {rel_path} ---")
        print(f"  Original:  {v_orig.size_mb:.1f} MB")
        print(f"  Optimized: {v_opt.size_mb:.1f} MB ({v_opt.size_mb/v_orig.size_mb*100:.1f}%)")
        print(f"  Location:  {os.path.dirname(v_orig.file_path)}")
        
        while True:
            choice = input("\nAction: [k]eep optimized, [o]riginal back, [s]kip, [q]uit: ").lower()
            if choice == 'k':
                finalize_pair(pair, "optimized")
                break
            elif choice == 'o':
                finalize_pair(pair, "original")
                break
            elif choice == 's':
                print("Skipped.")
                break
            elif choice == 'q':
                print("Goodbye!")
                return
            else:
                print("Invalid choice.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
