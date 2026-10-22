"""Deterministic synthetic prescription-image generator. Fictitious, non-clinical rules."""
from __future__ import annotations
import argparse
import json
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

MEDICINES=tuple(f'SYNTHMED-{x:02d}' for x in range(1,13))
FICTIONAL_MAX_SINGLE_MG=100
FICTIONAL_MAX_DAILY_MG=200
FICTIONAL_MIN_AGE_YEARS=12
FICTIONAL_MAX_AGE_YEARS=65
FONTS=('/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf',
       '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
       'C:/Windows/Fonts/segoeui.ttf')

def _font(size):
    for path in FONTS:
        try:return ImageFont.truetype(path,size)
        except OSError:continue
    return ImageFont.load_default()

def generate(output, *, count=400, seed=20261022, allow_small=False):
    if not isinstance(seed,int) or (not allow_small and not 300<=count<=500) or count<1:
        raise ValueError('Thesis synthetic dataset requires 300–500 images and a fixed integer seed')
    root=Path(output)
    root.mkdir(parents=True,exist_ok=True)
    folder=root/'images';folder.mkdir(exist_ok=True)
    rng=random.Random(seed)
    dataset=[]
    splits=['train']*int(count*.70)+['validation']*int(count*.15)
    splits+=['test']*(count-len(splits))
    rng.shuffle(splits)
    for index in range(count):
        medicine=rng.choice(MEDICINES)
        dose=rng.choice([10,25,50,75,100,125,150,200])
        frequency=rng.choice(['once daily','twice daily','three times daily'])
        times={'once daily':1,'twice daily':2,'three times daily':3}[frequency]
        age=rng.randint(2,90)
        weight=round(rng.uniform(14,105),1)
        lines=[
            'RESEARCH SYNTHETIC PRESCRIPTION — NOT FOR PATIENTS',
            f'Age: {age} years',
            f'Weight: {weight} kg',
            f'Medicine: {medicine}',
            f'Dose: {dose} mg',
            f'Frequency: {frequency}',
            'Route: oral',
            'Indication: fictional simulation',
            'Population: synthetic test'
        ]
        gold={'medicine':medicine,'dose':f'{dose} mg','frequency':frequency,
              'age':f'{age} years','weight':f'{weight} kg','route':'oral',
              'indication':'fictional simulation','population':'synthetic test'}
        image=Image.new('RGB',(1080,660),(250,249,244))
        draw=ImageDraw.Draw(image)
        for y in range(90,615,52):
            draw.line((65,y,1018,y),fill=(228,229,222),width=1)
        # Shift, tilt, blur and illumination are independently varied.
        xstart=rng.randint(65,110)
        tilt=rng.randint(-6,6)
        for j,line in enumerate(lines):
            font=_font(20 if j==0 else rng.randint(25,33))
            ink=rng.randint(18,75)
            draw.text((xstart+rng.randint(-11,15),35+j*63+rng.randint(-5,4)),
                      line,font=font,fill=(ink,ink+7,ink+17))
        image=image.rotate(tilt,resample=Image.Resampling.BICUBIC,expand=False,
                           fillcolor=(249,247,241))
        image=ImageEnhance.Brightness(image).enhance(rng.uniform(.70,1.05))
        if rng.random()<.68:
            image=image.filter(ImageFilter.GaussianBlur(rng.uniform(.15,1.1)))
        filename=f'synthetic_{index+1:04d}.png'
        image.save(folder/filename,optimize=True)
        dataset.append({
            'image_id':f'SYNTH-{seed}-{index+1:04d}',
            'image_path':f'images/{filename}',
            'dataset':'SYNTHETIC_FICTIONAL_NOT_CLINICAL',
            'split':splits[index],
            'human_verified':False,
            'reviewer_id':None,
            'gold_transcript':'\n'.join(lines),
            'gold':gold,
            'gold_alert':bool(dose>FICTIONAL_MAX_SINGLE_MG or dose*times>FICTIONAL_MAX_DAILY_MG),
            'gold_age_flag':bool(age<FICTIONAL_MIN_AGE_YEARS or age>FICTIONAL_MAX_AGE_YEARS),
            'synthetic_rule':{
                'max_single_mg':FICTIONAL_MAX_SINGLE_MG,
                'max_daily_mg':FICTIONAL_MAX_DAILY_MG,
                'min_age_years':FICTIONAL_MIN_AGE_YEARS,
                'max_age_years':FICTIONAL_MAX_AGE_YEARS}
        })
    manifest=root/'manifest.jsonl'
    manifest.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in dataset),encoding='utf-8')
    meta={'schema':'medsafe.synthetic_dataset.v1','count':count,'seed':seed,'manifest':str(manifest),
          'human_verified':False,'valid_for_clinical_evaluation':False,
          'note':'All medicine labels and dose limits are fictional. Generated truth is not independent human ground truth.',
          'splits':{x:splits.count(x) for x in ('train','validation','test')}}
    (root/'metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    return meta

def main(argv=None):
    parser=argparse.ArgumentParser(description='Generate 300–500 synthetic, fictional prescription pages')
    parser.add_argument('--output',type=Path,default=Path('01_data/synthetic/generated'))
    parser.add_argument('--count',type=int,default=400)
    parser.add_argument('--seed',type=int,default=20261022)
    args=parser.parse_args(argv)
    print(json.dumps(generate(args.output,count=args.count,seed=args.seed),indent=2))
if __name__=='__main__':main()
