#!/usr/bin/env python3
"""
generate_metadata.py
- parcourt images/ recursively
- utilise CLIP (transformers) pour associer chaque image à la meilleure "team" à partir de teams.txt
- sauvegarde metadata.json et metadata.csv
"""

import argparse
import json
from pathlib import Path
from PIL import Image
import torch
from transformers import CLIPProcessor, CLIPModel
from tqdm import tqdm
import csv
import os

def read_teams(teams_file):
    with open(teams_file, 'r', encoding='utf-8') as f:
        teams = [line.strip() for line in f if line.strip()]
    return teams

def make_prompts(team):
    return [
        f"a photo of a {team} football jersey",
        f"a {team} football shirt",
        f"{team} soccer jersey",
        f"the home kit of {team}",
        f"a {team} team jersey"
    ]

def collect_image_paths(images_dir):
    p = Path(images_dir)
    exts = {'.jpg', '.jpeg', '.png', '.webp'}
    files = [f for f in p.rglob('*') if f.is_file() and f.suffix.lower() in exts]
    return sorted(files)

def compute_team_embeddings(model, processor, teams, device):
    # build prompt list and mapping
    prompts = []
    prompt_team_idx = []
    for i, team in enumerate(teams):
        ps = make_prompts(team)
        prompts.extend(ps)
        prompt_team_idx.extend([i]*len(ps))

    # compute text embeddings in batches
    text_embs = []
    batch = 64
    for i in range(0, len(prompts), batch):
        batch_prompts = prompts[i:i+batch]
        inputs = processor(text=batch_prompts, return_tensors='pt', padding=True).to(device)
        with torch.no_grad():
            emb = model.get_text_features(**inputs)   # (B, D)
            emb = torch.nn.functional.normalize(emb, p=2, dim=-1)
            text_embs.append(emb.cpu())
    text_embs = torch.cat(text_embs, dim=0)  # (P, D)

    # aggregate per team (mean of prompts)
    teams_emb = []
    for idx in range(len(teams)):
        inds = [i for i,p in enumerate(prompt_team_idx) if p==idx]
        team_emb = text_embs[inds].mean(dim=0)
        team_emb = torch.nn.functional.normalize(team_emb, p=2, dim=-1)
        teams_emb.append(team_emb)
    teams_emb = torch.stack(teams_emb, dim=0)  # (T, D)
    return teams_emb

def process_images_and_match(model, processor, images, teams_emb, teams, device, batch_size=8, threshold=0.20):
    results = {}
    for i in tqdm(range(0, len(images), batch_size), desc="Processing images"):
        batch_paths = images[i:i+batch_size]
        pil_imgs = []
        rel_paths = []
        for p in batch_paths:
            try:
                img = Image.open(p).convert('RGB')
                pil_imgs.append(img)
                # relative path from images/ root
                rel = str(p.relative_to(images_root))
                rel_paths.append(rel.replace("\\","/"))
            except Exception as e:
                print(f"Could not open {p}: {e}")
                pil_imgs.append(Image.new('RGB', (224,224), color=(255,255,255)))
                rel_paths.append(str(p.name))

        inputs = processor(images=pil_imgs, return_tensors='pt').to(device)
        with torch.no_grad():
            img_emb = model.get_image_features(**inputs)  # (B, D)
            img_emb = torch.nn.functional.normalize(img_emb, p=2, dim=-1).cpu()

        # cosine similarities with teams (B x T)
        sims = img_emb @ teams_emb.T  # (B, T)
        for j in range(sims.size(0)):
            s = sims[j]
            topv, topi = torch.topk(s, k=1)
            score = float(topv.item())
            team_idx = int(topi.item())
            predicted = teams[team_idx] if score >= threshold else "unknown"
            results[rel_paths[j]] = {"team": predicted, "score": score}
    return results

def save_outputs(results, json_out, csv_out):
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    # CSV
    with open(csv_out, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['path','team','score'])
        for k,v in results.items():
            writer.writerow([k, v.get('team',''), v.get('score',0)])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--images_dir', type=str, default='images', help='dossier racine images')
    parser.add_argument('--teams_file', type=str, default='teams.txt', help='fichier liste d equipes')
    parser.add_argument('--output_json', type=str, default='metadata.json')
    parser.add_argument('--output_csv', type=str, default='metadata.csv')
    parser.add_argument('--batch_size', type=int, default=8)
    parser.add_argument('--threshold', type=float, default=0.20)
    args = parser.parse_args()

    images_root = Path(args.images_dir)
    if not images_root.exists():
        raise SystemExit(f"images_dir {images_root} not found")

    teams = read_teams(args.teams_file)
    if len(teams)==0:
        raise SystemExit("teams.txt vide ; ajoute des noms d'equipe (1 par ligne)")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}. Found {len(teams)} teams.")

    print("Loading CLIP model (this télécharge des poids la première fois)...")
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

    print("Computing team embeddings...")
    teams_emb = compute_team_embeddings(model, processor, teams, device)

    print("Collecting images...")
    images = collect_image_paths(args.images_dir)
    print(f"Found {len(images)} images")

    results = process_images_and_match(model, processor, images, teams_emb, teams, device, batch_size=args.batch_size, threshold=args.threshold)

    print(f"Saving results to {args.output_json} and {args.output_csv}")
    save_outputs(results, args.output_json, args.output_csv)
    print("Terminé.")
