all: collect verify analyze analyze-sites figures figures-sites

collect:
	python src/collect.py --plan tags
	python src/collect.py --plan sites
verify:
	python src/verify_sitewide.py
analyze:
	python src/analyze.py
analyze-sites:
	python src/analyze_sites.py
figures:
	python src/figures.py
figures-sites:
	python src/figures_sites.py

# 生成 GitHub Pages 用的目录（Settings -> Pages -> main /docs）
docs:
	mkdir -p docs
	cp outputs/dashboard/index.html docs/index.html
	cp outputs/report.md docs/report.md
	mkdir -p docs/figures && cp outputs/figures/*.png docs/figures/

.PHONY: all collect verify analyze analyze-sites figures figures-sites docs
