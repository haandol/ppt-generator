#!/usr/bin/env python3
"""Bedrock Titan Image Generator V2 wrapper.

Usage:
    python generate_images.py "a futuristic city" output.png
    python generate_images.py "a cat on a cloud" cat.png --width 1024 --height 1024 --cfg 10
    python generate_images.py --batch images.json
    
Batch JSON format:
    [
        {"prompt": "a futuristic city", "output": "city.png"},
        {"prompt": "a cat", "output": "cat.png", "width": 1024, "height": 1024}
    ]
"""
import argparse, subprocess, json, base64, os, sys


def generate(prompt, output, width=1280, height=768, cfg=8.0, region="us-east-1", model="amazon.titan-image-generator-v2:0"):
    body = json.dumps({
        "textToImageParams": {"text": prompt},
        "taskType": "TEXT_IMAGE",
        "imageGenerationConfig": {"numberOfImages": 1, "height": height, "width": width, "cfgScale": cfg}
    })
    tmp = output + ".tmp.json"
    r = subprocess.run(
        ["aws", "bedrock-runtime", "invoke-model", "--region", region, "--model-id", model,
         "--accept", "application/json", "--content-type", "application/json", "--body", body, tmp],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"  FAIL {output}: {r.stderr.strip()}", file=sys.stderr)
        return False

    with open(tmp) as f:
        data = json.load(f)
    os.remove(tmp)

    if data.get("images"):
        os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
        with open(output, "wb") as f:
            f.write(base64.b64decode(data["images"][0]))
        print(f"  OK {output}")
        return True
    print(f"  FAIL {output}: {data.get('error', 'unknown')}", file=sys.stderr)
    return False


def main():
    p = argparse.ArgumentParser(description="Generate images with Bedrock Titan Image Generator V2")
    p.add_argument("prompt", nargs="?", help="Text prompt")
    p.add_argument("output", nargs="?", help="Output PNG path")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=768)
    p.add_argument("--cfg", type=float, default=8.0)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--batch", help="JSON file with batch of {prompt, output, width?, height?, cfg?}")
    args = p.parse_args()

    if args.batch:
        with open(args.batch) as f:
            items = json.load(f)
        ok = sum(generate(i["prompt"], i["output"], i.get("width", args.width), i.get("height", args.height), i.get("cfg", args.cfg), args.region) for i in items)
        print(f"\n{ok}/{len(items)} images generated.")
    elif args.prompt and args.output:
        generate(args.prompt, args.output, args.width, args.height, args.cfg, args.region)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
