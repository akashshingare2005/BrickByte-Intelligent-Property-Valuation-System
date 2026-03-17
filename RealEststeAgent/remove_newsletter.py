import os
import glob
import re

template_dir = r"c:\Users\Lenovo\OneDrive\Desktop\Real Estste Agent\RealEststeAgent\RealEststeAgent\templates"
files = glob.glob(os.path.join(template_dir, "*.html"))

# Matches the exact structure of the Newsletter col-lg-3 block
pattern = re.compile(r'\s*<div class="col-lg-3 col-md-6">\s*<h5 class="text-white mb-4">Newsletter</h5>.*?</button>\s*</div>\s*</div>', re.DOTALL)

total_replaced = 0
for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    new_content, count = pattern.subn('', content)
    if count > 0:
        with open(f, 'w', encoding='utf-8') as file:
            file.write(new_content)
        print(f"Replaced {count} instances in {os.path.basename(f)}")
        total_replaced += count

print(f"Total files updated: {total_replaced}")
