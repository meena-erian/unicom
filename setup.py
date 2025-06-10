from setuptools import setup, find_packages

setup(
    name='django-unicom',
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
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
        'psycopg2-binary>=2.9,<3.0',
        'urllib3>=2.4.0,<3.0',
        'dnspython>=2.7.0,<3.0',
        'requests>=2.31.0,<3.0',
        'IMAPClient>=3.0.1',
        'dnspython>=2.7.0,<3.0',
        'Pillow>=10.4.0',
        'django-ace>=1.39.2',
        'fa2svg==0.1.6',
        'pytz>=2024.1',
        'openai',
    ],
    extras_require={
        'dev': [
            'pytest>=8.3.5,<9.0',
            'pytest-django>=4.11.1,<5.0',
            'charset-normalizer>=3.1.0,<4.0',
            'python-dotenv>=1.0,<2.0',
        ],
    },
    classifiers=[
        'Framework :: Django',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
    ],
)
