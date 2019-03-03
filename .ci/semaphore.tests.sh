set -e -x

cp requirements.txt requirements.orig
printf '%s\n%s\n%s\n%s\n' \
    "git+https://github.com/coala/coala" \
    "git+https://github.com/coala/coala-bears" \
    "$(cat test-requirements.txt)" \
    "$(cat requirements.txt)" \
    > requirements.txt
pip install -r requirements.txt
coala --ci -V
python -m pytest
codecov
