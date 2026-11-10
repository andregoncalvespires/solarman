# Solarman (Deye) para Home Assistant

Fork mantido da integração [StephanJoubert/home_assistant_solarman](https://github.com/StephanJoubert/home_assistant_solarman),
que foi arquivada. Comunicação local (porta 8899) com data loggers Solarman V5 e inversores Deye e outros.

> Instalação: HACS → Repositórios personalizados → `andregoncalvespires/solarman` (categoria *Integração*).
> O domínio continua `solarman`, então substitui a instalação anterior sem recriar entidades.

## O que este fork acrescenta

- **Consultas cientes do sol**: não tenta conectar após o pôr do sol (sem logs de aviso à noite).
- **Sensores calculados nativos** (para todo perfil com `PVn Voltage` + `PVn Current`):

  | Entidade | Descrição |
  |---|---|
  | `PVn Power` (W) | tensão × corrente de cada entrada/módulo |
  | `PV Total Power` (W) | soma dos módulos |
  | `AC Output Load` (%) | potência CA ÷ capacidade (registrador *Rated Power* ou valor informado) |
  | `PVn Relative Output` (%) | produção do módulo ÷ mediana dos demais (diagnóstico) |

  À noite / sem conexão, potências e carga valem `0` (como nos templates antigos).
  Nomes já existentes no perfil (ex.: `PV1 Power` nos híbridos) não são redefinidos.

- **`PV Problem`** (binary_sensor, classe *problem*): liga quando um módulo produz muito menos que os
  outros do mesmo inversor. Atributos: `problem_modules`, `problem_since`, `hint`, `relative_output`,
  `monitored_inputs`.

  Regras (ajustáveis em *Configurar*):
  - cada módulo é comparado com a **mediana dos outros**; nuvem afeta todos igual e não dispara;
  - só avalia com inversor conectado, sol acima de 15° e referência ≥ 50 W;
  - liga após **30 min** de amostras válidas abaixo de **50 %**; desliga após 10 min acima de 70 %;
  - à noite o relógio pausa e o estado é mantido (e restaurado após reiniciar o HA);
  - exige ao menos 3 entradas monitoradas; **desmarque entradas sem painel**;
  - com 4 entradas detecta até 2 módulos ruins ao mesmo tempo (3 ou 4 não dá para distinguir);
  - `hint`: `open_circuit_suspected` (≈0 V: conector/cabo/painel), `voltage_without_current`
    (tensão sem corrente: entrada do micro), `low_output`.

- Correções: recarga ao alterar opções (antes gerava `KeyError`), *blocking call*, caminho das
  definições relativo ao arquivo.

### Exemplo de automação

```yaml
automation:
  - alias: Alerta módulo solar
    trigger:
      - platform: state
        entity_id: binary_sensor.solarman_hacs_leste_pv_problem
        to: "on"
    action:
      - service: notify.notify
        data:
          message: >
            Módulo(s) {{ state_attr(trigger.entity_id, 'problem_modules') | join(', ') }}
            com produção anormal desde {{ state_attr(trigger.entity_id, 'problem_since') }}.
```

## Desenvolvimento

```bash
pip install pytest pyyaml pytest-homeassistant-custom-component pysolarmanv5
pytest -q
```

Versão: Actions → **Release** → *Run workflow* (patch/minor/major). Atualiza o `manifest.json`,
cria a tag `vX.Y.Z` e publica o Release com `solarman.zip`.

## Licença e atribuição

Apache License 2.0 (ver `LICENSE` e `NOTICE`). O código-base é do projeto upstream
[StephanJoubert/home_assistant_solarman](https://github.com/StephanJoubert/home_assistant_solarman);
as modificações deste fork estão descritas acima.
