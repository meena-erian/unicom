from setuptools import setup, find_packages

setup(
    name='django-unicom',
    version='0.1.0',
    description='Unified communication layer for Django (Telegram, WhatsApp, Email)',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Meena (Menas) Erian',
    author_email='hi@menas.pro',
    url='https://github.com/meena-erian/unicom',
    packages=find_packages(exclude=['tests*']),
    include_package_data=True,
    install_requires=[
        'Django>=3.2',
    ],
    extras_require={
        'dev': [
            'pytest',
            'pytest-django',
        ],
    },
    classifiers=[
        'Framework :: Django',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
    ],
)
