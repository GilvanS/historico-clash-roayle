#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verifica se o CSS do radar está sendo aplicado corretamente"""
import os

# Verificar CSS
with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

# CSS selectors
css_selectors = [".rd-section", ".rd-header", ".rd-badge", ".rd-grid", ".rd-clan", ".rd-clan-me"]
# HTML classes
html_classes = ["rd-section", "rd-header", "rd-grid", "rd-clan"]

print("=== VERIFICACAO DO CSS DO RADAR ===\n")

print("CSS (estilos):")
for sel in css_selectors:
    if sel in content:
        print(f"  [OK] {sel} encontrado")
    else:
        print(f"  [ERRO] {sel} NAO encontrado")

print("\nHTML (classes):")
for cls in html_classes:
    count = content.count(f'class="{cls}"') + content.count(f"class='{cls}'")
    print(f"  {cls}: {count} ocorrencias")

print("\n=== FIM DA VERIFICACAO ===")