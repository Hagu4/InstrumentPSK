import codecs
import re

files = [
    r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\templates\app\login.html',
    r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\templates\app\registration.html'
]

for path in files:
    with codecs.open(path, 'r', 'utf-8') as f:
        content = f.read()

    # 1. Image styles: remove fixed width/height and add contain
    content = re.sub(r'\.auth-logo img \{.*?\}', """    .auth-logo img {
        height: 48px;
        width: auto;
        object-fit: contain;
    }""", content, flags=re.DOTALL)

    # 2. Span styles: make text bolder and uppercase
    content = re.sub(r'\.auth-logo span \{.*?\}', """    .auth-logo span {
        font-size: 2rem;
        font-weight: 900;
        color: #0f172a;
        letter-spacing: -1px;
        text-transform: uppercase;
    }""", content, flags=re.DOTALL)

    with codecs.open(path, 'w', 'utf-8') as f:
        f.write(content)

print("Logo styles fixed correctly.")
