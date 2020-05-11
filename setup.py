from distutils.core import setup

project_name = "Tidepool Data Science Project"
version = "0.1.0"
author = "Ed Nykaza"
author_email = "ed@tidepool.org"
package_name = "how_loop_dosing_works"  # this is the thing you actually import

setup(
    name=project_name,
    version=version,
    author=author,
    author_email=author_email,
    packages=[package_name],  # add subpackages too
    package_dir={package_name: 'src'},
    license='BSD 2-Clause',
    long_description=open('README.md').read(),
    python_requires='>=3.6',
)
