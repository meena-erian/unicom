from setuptools import setup, find_packages

setup(
    name='django-unicom',
    version='0.1.1',
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
        'requests>=2.31.0,<3.0',
        'IMAPClient>=3.0.1',
        'dnspython>=2.7.0,<3.0',
        'Pillow>=10.4.0'
    ],
    extras_require={
        'dev': [
            'pytest>=8.3.5,<9.0',
            'pytest-django>=4.11.1,<5.0',
            'charset-normalizer>=3.1.0,<4.0',
            'python-dotenv>=1.0,<2.0'
        ],
    },
    classifiers=[
        'Framework :: Django',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
    ],
)
