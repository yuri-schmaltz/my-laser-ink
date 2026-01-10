# Arquitetura (Laser Suite)

## Objetivo
Construir um produto desktop (fácil de usar) para corte/gravação a laser, com foco inicial em GRBL via serial e expansão por drivers.

## Princípios
- Uma UI principal (produto) + módulos internos bem isolados.
- Padrões abertos: SVG/DXF/PDF/PNG; projetos/configurações em JSON/YAML.
- Robustez no streaming serial: logs, retry controlado, cancelamento seguro.
- Extensibilidade por “capabilities” do dispositivo (drivers plugáveis).

## Componentes
### apps/desktop
Aplicação principal (UI + fluxo do usuário). Deve depender de APIs internas (packages/*).

### packages/core
Modelos de dados (Project, Job, CamOps, Material Library) + validações e serialização.

### packages/device_api
Contrato único para comunicação com hardware:
- DeviceDriver (connect/disconnect/status)
- stream de job/G-code
- comandos de operação (jog/home/frame/pause/resume/abort)
- capacidades (supports_m4, max_s_value etc.)

### packages/drivers/*
Implementações concretas da DeviceDriver (GRBL primeiro, outros depois).

## Fluxo de dados (alto nível)
Importação (SVG/DXF/PDF/PNG) -> Scene/Project -> CAM (vetor/raster) -> Job -> Post (G-code) -> Spooler -> Driver (serial) -> Dispositivo

## Segurança
- “Arm” explícito para habilitar laser.
- Laser sempre OFF em deslocamentos.
- Abort/Stop imediato e previsível.
- Checagens de bounds e soft-limits quando aplicável.
