# Layout do Repositório

## Diretórios
- apps/desktop: aplicação principal (Laser Ink como base)
- packages/core: modelos e lógica de projeto/CAM
- packages/device_api: interface estável de drivers e spooler
- packages/drivers: drivers concretos (grbl, etc.)
- services: serviços auxiliares (opcional; ex.: bridge)
- docs: documentação
- tools: scripts de QA, simuladores de serial

## Convenções
- Todo novo módulo deve ter README mínimo.
- Configurações abertas em YAML/JSON dentro de `configs/` (quando criado).
- Sem dependência direta de drivers no UI: sempre via device_api.

