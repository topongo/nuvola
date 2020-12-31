import setuptools

with open("README.md") as f:
      LONGDESCRIPTION = f.read()

setuptools.setup(
      name='nuvola',
      version='0.3',
      description="Python API for the electronic register Nuvola from Madisoft",
      url='https://github.com/topongo/nuvola',
      author='Lorenzo Bodini',
      author_email='lorenzo.bodini.private@gmail.com',
      packages=['nuvola'],
      python_requires='>=3.8',
      license="GPL3",
      platform="All",
      long_description=LONGDESCRIPTION,
      long_description_content_type="text/markdown",
)
