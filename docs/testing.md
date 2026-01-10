# Testes e QA

## Objetivos
- Evitar regressões no spooler/serial (alto risco).
- Validar geração de G-code (golden files).
- Garantir que o app inicia e executa fluxos básicos.

## Tipos de teste
- Unitários: parsing de status, escalas de potência, bounds
- Integração: simulador serial, execução de jobs, pause/resume/abort
- Golden files: cena -> G-code esperado

## Ferramentas
- Pytest
- Simulador serial (tools/qa)
- Logs exportáveis por job

## Critérios de aceite mínimos
- Sem travamentos em job longo
- Sem laser ligado em G0
- Abort sempre retorna a estado seguro
