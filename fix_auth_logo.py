import codecs
import re

files = [
    r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\templates\app\login.html',
    r'D:\Studies\Lab and pars\Web-ProgDJ(2)\DjangoWebProject1\DjangoWebProject1\app\templates\app\registration.html'
]

for path in files:
    with codecs.open(path, 'r', 'utf-8') as f:
        content = f.read()

    # Update logo container styles
    content = content.replace('gap: 16px;', 'gap: 12px;')
    
    # Update image styles to prevent stretching
    old_img_css = """    .auth-logo img {
        width: 60px;
        height: 60px;
    }"""
    
    new_img_css = """    .auth-logo img {
        height: 50px;
        width: auto;
        object-fit: contain;
    }"""
    content = content.replace(old_img_css, new_img_css)
    
    # Update span (text) styles
    old_span_css = """    .auth-logo span {
        font-size: 1.8rem;
        font-weight: 800;
        color: #1e293b;
        letter-spacing: -0.5px;
    }"""
    
    new_span_css = """    .auth-logo span {
        font-size: 2.2rem;
        font-weight: 900;
        color: #0f172a;
        letter-spacing: -1px;
        text-transform: uppercase;
    }"""
    
    if old_span_css in content:
        content = content.replace(old_span_css, new_span_css)
    else:
        # Fallback if the previous replacement changed it or it's slightly different
        content = re.sub(r'\.auth-logo span \{.*?\}', new_span_css, content, flags=re.DOTALL)

    with codecs.open(path, 'w', 'utf-8') as f:
        f.write(content)

print("Logo styles updated locally.")
