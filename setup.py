import setuptools

VERSION = "1.4"

with open("README.md") as f:
    LONGDESCRIPTION = f.read()
with open("nuvola/version.py", "w+") as f:
    f.write(f"VERSION = {VERSION}\n")

setuptools.setup(
    name='nuvola',
    version=VERSION,
    description="Python API for the electronic register Nuvola from Madisoft",
    url='https://github.com/topongo/nuvola',
    author='Lorenzo Bodini',
    author_email='lorenzo.bodini.private@gmail.com',
    packages=['nuvola'],
    python_requires='>=3.7',
    license="GPL3",
    platform="All",
    long_description=LONGDESCRIPTION,
    long_description_content_type="text/markdown",
    install_requires=[
        "bs4",
        "requests",
        "datetime",
        "simplejson"
    ]
)
