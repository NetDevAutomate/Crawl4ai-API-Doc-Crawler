import os

with open('crawl4ai_reference.md', 'a') as outfile:
    dir = 'output/crawl4ai'
    files = sorted(os.listdir(dir))
    for file in files:
        if file.endswith('.md'):
            with open(os.path.join(dir, file), 'r') as infile:
                outfile.write('\n\n' + infile.read())
