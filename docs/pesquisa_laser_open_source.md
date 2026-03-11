# Pesquisa: alternativas open source ao LightBurn (laser cutter/engraver)

**Data da pesquisa:** 2026-01-10  
**Escopo:** softwares open source para preparação (importação + CAM) e/ou controle (sender) de máquinas de corte/gravação a laser, com foco em **GRBL 1.1 e similares via serial**. Inclui também opções **Galvo/Fibra** quando open source.

---

## 1) Resumo executivo (o que mais se aproxima do “pacote LightBurn”)

### Candidatos mais completos (bom ponto de partida para evolução / fork / estudo arquitetural)

1. **MeerK40t** — “suite” completa e extensível, com suporte a **K40**, **GRBL** e até **controladores JCZ (Ezcad2) para galvo** (ainda com ressalvas/experimental em alguns fluxos).  
2. **Laser Ink** — software moderno de controle para **GRBL**, com forte foco em **usabilidade**, importação ampla (SVG/DXF/PDF/PNG) e recursos “produtivos” (ex.: câmera/alinhamento e otimizações de caminho).  
3. **LaserWeb4 / CNCWeb** — aplicação “full CAM + controle” com foco em geração de G-code a partir de DXF/SVG/bitmaps e suporte a múltiplos firmwares (GRBL, Smoothieware, TinyG, Marlin etc.).  
4. **VisiCut + LibLaserCut** — tradicional em ambientes de FabLab/educação; separa bem a camada de UI do backend de comunicação; suporta múltiplos cutters via biblioteca.

### Bons complementos (para referência, comparação ou reaproveitamento parcial)

- **LaserGRBL** — referência de UX “simples e direta” para GRBL (Windows), com bom pipeline de raster/bitmap para hobby.  
- **K40 Whisperer** — referência clássica e enxuta para K40 (controladora stock), com foco em SVG/DXF.  
- **bCNC / Candle** — “senders” e utilitários de G-code que ajudam a estudar robustez de streaming/serial e UI de controle.  
- **Kiri:Moto** — CAM web (gera toolpaths/G-code para laser); útil como referência para pipeline de geometria e UX de CAM no navegador.
- **Balor / OPAL (OpenGalvo)** — bases open source para ecossistema **Galvo** (CLI e firmware).

---

## 2) Ferramentas analisadas (principais)

### 2.1 MeerK40t (MIT) — *desktop + console extensível*
- **Escopo:** desenho/importação + operações (vetor/raster) + controle/driver; possui console e CLI.  
- **Dispositivos:** K40 (Lihuiyu), GRBL, Moshiboard e **JCZ/Ezcad2 galvo**; inclui “middleman” de emulação em alguns cenários.  
- **Plataformas:** Windows/macOS/Linux (incl. Raspberry Pi por extensão).  
- **Por que é boa base:** arquitetura extensível, foco declarado em “platform para desenvolvedores”, suporte multi-hardware.

### 2.2 Laser Ink (MIT) — *controle moderno para GRBL*
- **Escopo:** importação + preparação + envio/controle; voltado a **GRBL-based lasers**.  
- **Formatos:** **SVG, DXF, PDF, PNG** (e documentação detalhada para importação/limpeza).  
- **Plataformas:** Linux e Windows; **sem builds oficiais para macOS** (até o momento).  
- **Destaques de produto:** documentação ativa, instalador (ex.: Snap), suporte a câmera/alinhamento e interface moderna (Gtk4/Libadwaita).

### 2.3 LaserWeb4 / CNCWeb (AGPL-3.0) — *CAM + controle multi-firmware*
- **Escopo:** geração de **G-code** a partir de **DXF/SVG/bitmaps** e controle de máquina.  
- **Firmwares:** GRBL (>=1.1), grbl-LPC, Smoothieware, TinyG, Marlin/MarlinKimbra (com diferentes níveis de maturidade).  
- **Arquitetura:** front-end (Chrome) + servidor de comunicação (**lw.comm-server**).  
- **Observação de maturidade:** o ecossistema tem histórico de releases antigas (binaries com “latest” em 2021), embora haja atividade de commits no repositório.

### 2.4 VisiCut (LGPL-3.0) + LibLaserCut — *pipeline clássico e “limpo”*
- **Escopo:** preparar, salvar e enviar jobs; forte em organização por camadas/cores e configuração de materiais.  
- **Formatos (documentação do projeto):** SVG, EPS, DXF e o formato de projeto **PLF** (Portable Laser Format).  
- **LibLaserCut:** biblioteca de comunicação com diferentes modelos/controladoras, reutilizável por outros front-ends.

---

## 3) Ferramentas relevantes (parciais/específicas)

### 3.1 LaserGRBL (GPLv3) — *GRBL (Windows), foco em hobby e simplicidade*
- **Pontos fortes:** UX simples, pipeline raster para imagens/logos, compatível com GRBL 0.9 e 1.1, atenção a problemas de drivers USB-serial (ex.: CH340).  
- **Limitações:** escopo menos “CAD/CAM completo” do que LightBurn; foco em GRBL e Windows.

### 3.2 K40 Whisperer (GPL) — *K40 stock controller*
- **Pontos fortes:** “mínimo necessário” para K40; lê **SVG e DXF** e envia ao controlador; base didática para drivers proprietários (USB).  
- **Limitações:** muito específico para K40; pipeline e UI mais tradicionais.

### 3.3 bCNC (GPL) e Candle (GPL) — *senders/generalistas*
- **Uso típico aqui:** referência de streaming robusto, UI de console/jog, visualização de G-code e plugins (bCNC).  
- **Limitações:** não competem diretamente com LightBurn em “toolpath + camadas/material” (dependendo do fluxo).

### 3.4 Kiri:Moto (MIT) — *CAM web (inclui modo laser)*
- **Valor como base:** pipeline de toolpaths e UX de CAM em browser; pode inspirar módulos de importação/otimização.

---

## 4) Galvo/Fibra (open source) — bases para DSP/galvo

### 4.1 Balor (GPLv3+) — *CLI para controladoras BJJCZ (Ezcad2)*
- **Escopo:** controle via linha de comando e engenharia reversa de placas JCZ; referência para comunicação, comandos e pipeline de marcação.

### 4.2 OpenGalvo OPAL — *firmware G-code -> XY2-100 (Teensy)*
- **Escopo:** processar comandos G-code e gerar sinal **XY2-100** para galvos digitais; base para arquiteturas em que o host fala “G-code”, mas o hardware exige protocolo galvo.

### 4.3 galvoplotter / integração Balor + MeerK40t
- **galvoplotter:** sistema de comandos de baixo nível para controladores BJJCZ.  
- **balor-meerk40t:** plugin/ponte que integra Balor ao MeerK40t.

---

## 5) Matriz de comparação (resumo)

| Projeto | Escopo (alto nível) | Alvos principais | Formatos de entrada citados | Licença | Plataformas (citadas) | Observações rápidas |
|---|---|---|---|---|---|---|
| MeerK40t | Suite (import + operações + controle) | K40, GRBL, JCZ/Ezcad2 (galvo) | (varia por módulo; foco em fluxo laser) | MIT | Win/macOS/Linux | Muito extensível; bom “core” para evoluir |
| Laser Ink | Import + preparar + controle | GRBL | SVG, DXF, PDF, PNG | MIT | Linux/Windows | UI moderna; docs fortes; sem build oficial macOS |
| LaserWeb4 | CAM + controle via servidor | GRBL, grbl-LPC, Smoothieware, TinyG, Marlin* | DXF, SVG, bitmap/JPG/PNG | AGPL-3.0 | Win/macOS/Linux (x86/x64) | Arquitetura web + comm-server; ecossistema com releases antigas |
| VisiCut | Preparar + enviar jobs | vários cutters via LibLaserCut | SVG, EPS, DXF, PLF | LGPL-3.0 | multi-plataforma | Arquitetura clássica; boa separação de camadas |
| LaserGRBL | Controle + raster simples | GRBL 0.9/1.1 | imagens (pipeline próprio) | GPLv3 | Windows | Referência de UX simples para GRBL |
| K40 Whisperer | Preparar + enviar | K40 (M2 Nano etc.) | SVG, DXF | GPL | (varia por empacotamento) | Projeto enxuto e didático para K40 |
| bCNC | Sender + editor + plugins | GRBL/grblHAL | G-code | GPL | Win/Linux/macOS | Excelente para estudar streaming/robustez |
| Candle | Sender + visualizador | GRBL | G-code | (GPL no ecossistema) | Win/Linux (mac via forks) | UI Qt; releases recentes |
| Kiri:Moto | CAM (web) | Laser/CNC/3DP | (varia) | MIT | Browser | Bom para estudar CAM em JS |
| Balor | CLI | BJJCZ (galvo) | (foco em comandos) | GPLv3+ | multi-plataforma | Base para galvo via engenharia reversa |
| OPAL (OpenGalvo) | Firmware | XY2-100 galvo | G-code (entrada) | (ver repo) | Teensy | Ponte G-code -> XY2-100 |

\* suporte Marlin citado como “não finalizado” em alguns pontos do ecossistema LaserWeb.

---

## 6) Observações práticas para um produto “fácil, robusto e com padrões abertos”
- **Separar bem as camadas:** UI/edição + pipeline de importação/normalização (SVG/DXF/PDF) + CAM/otimização + “driver layer” (serial/USB/protocolos). VisiCut/LibLaserCut e LaserWeb (comm-server) mostram abordagens diferentes para isso.  
- **Formato de projeto aberto:** manter um “project file” versionado (ex.: JSON + assets embutidos/referenciados), evitando lock-in.  
- **Perfis de máquina e material:** estrutura declarativa (ex.: YAML/JSON) para bibliotecas de materiais, velocidades, potências, modos (M3/M4), passes etc.  
- **Robustez no streaming serial:** inspirar-se em senders maduros (Candle/bCNC) e em ferramentas com foco em diagnóstico (LaserGRBL).  
- **Galvo/DSP:** tratar como “driver/protocolo” separado; Balor/galvoplotter e OPAL indicam caminhos complementares (host->JCZ vs host->G-code->XY2-100).

---

## 7) Referências (fontes principais)

1. LaserWeb4 (repo): https://github.com/LaserWeb/LaserWeb4  
2. LaserWeb / CNCWeb (site): https://laserweb.yurl.ch/  
3. LaserWeb “Supported firmwares”: https://laserweb.yurl.ch/documentation/compatibility/54-supported-firmwares  
4. lw.comm-server (repo): https://github.com/LaserWeb/lw.comm-server  
5. LaserWeb4-Binaries (releases): https://github.com/LaserWeb/LaserWeb4-Binaries  
6. MeerK40t (repo): https://github.com/meerk40t/meerk40t  
7. MeerK40t releases (exemplo): https://github.com/meerk40t/meerk40t/releases  
8. Laser Ink (docs): https://rayforge.org/docs/latest/  
9. Laser Ink “File formats”: https://rayforge.org/docs/latest/files/index.html  
10. Laser Ink (PyPI): https://pypi.org/project/rayforge/  
11. Laser Ink (Snap): https://snapcraft.io/rayforge  
12. VisiCut (repo): https://github.com/t-oster/VisiCut  
13. VisiCut (site): https://visicut.org/  
14. LibLaserCut (repo): https://github.com/t-oster/LibLaserCut  
15. LaserGRBL (repo): https://github.com/arkypita/LaserGRBL  
16. LaserGRBL (releases): https://github.com/arkypita/LaserGRBL/releases  
17. K40 Whisperer (site): https://www.scorchworks.com/K40whisperer/k40whisperer.html  
18. bCNC (repo): https://github.com/vlachoudis/bCNC  
19. Candle (repo): https://github.com/Denvi/Candle  
20. Kiri:Moto (repo): https://github.com/GridSpace/grid-apps  
21. Balor (GitLab): https://gitlab.com/bryce15/balor  
22. OPAL (OpenGalvo): https://github.com/opengalvo/OPAL  
23. galvoplotter: https://github.com/meerk40t/galvoplotter  
24. balor-meerk40t: https://github.com/tatarize/balor-meerk40t  

