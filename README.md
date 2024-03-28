<div align="center">
<h1>USST-CS-2024-Backend</h1>

<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</div>

## Development

### Setup

```bash
pip install -r requirements.txt
```

### Run

#### PyCharm

1. Open the project in PyCharm.
2. Add `config.yaml` at `/src/config.yaml`.
3. Set environment variables `DEVELOPMENT` to `True`.
4. Run `main.py`.

#### Terminal

```bash
cd src
export DEVELOPMENT=True
python .
```

or

```bash
cd src 
python . --dev
```

## Code Formatting

Please use [black](https://github.com/psf/black) for code formatting.

```bash
black .
```
