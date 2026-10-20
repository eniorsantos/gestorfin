# 02 · Dados da CVM

Base: `https://dados.cvm.gov.br/dados/CIA_ABERTA` (configurável em `CVM_BASE_URL`).

| Conjunto | URL (padrão) | Conteúdo |
|---|---|---|
| Cadastro | `/CAD/DADOS/cad_cia_aberta.csv` | companhias abertas (CD_CVM, CNPJ, nome, setor, situação) |
| DFP | `/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip` | demonstrações anuais |
| ITR | `/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip` | demonstrações trimestrais |
| IPE | `/DOC/IPE/DADOS/ipe_cia_aberta_{ano}.zip` | índice de documentos (fatos relevantes etc.) com link por documento |

> Estrutura descrita conforme a documentação pública da CVM e o conhecimento dos arquivos; **confira os cabeçalhos reais** na primeira carga. Se algo divergir, ajuste `cvm/load.py` (`_FILE_RE`, nomes de coluna).

## Estrutura dos zips DFP/ITR
Um CSV por (demonstração × consolidação): `dfp_cia_aberta_DRE_con_2023.csv`, `…_BPA_ind_2023.csv` etc. Separador `;`, encoding **latin-1**.

Demonstrações carregadas por padrão: `DRE`, `BPA`, `BPP` (configurável: `--statements DRE,BPA,BPP,DFC_MD,DFC_MI,DVA,DRA`).

### Colunas usadas
`CNPJ_CIA, DT_REFER, VERSAO, DENOM_CIA, CD_CVM, MOEDA, ESCALA_MOEDA, ORDEM_EXERC, DT_INI_EXERC, DT_FIM_EXERC, CD_CONTA, DS_CONTA, VL_CONTA, ST_CONTA_FIXA`

## Regras de transformação (`transform_frame`)
| Regra | Por quê |
|---|---|
| Só `ORDEM_EXERC = ÚLTIMO` | `PENÚLTIMO` repete o exercício anterior (duplicaria dados) |
| Só a maior `VERSAO` por (CD_CVM, DT_REFER) | reapresentações substituem versões anteriores |
| `VL_CONTA × 1000` se `ESCALA_MOEDA = MIL` | tudo em **reais** no banco; exibição em R$ mil nos cartões |
| Remove nulos e duplicatas (CD_CVM, DT_REFER, DT_INI, CD_CONTA) | integridade |
| Carga idempotente | apaga as (data-base, demonstração, consolidação) tocadas e reinsere |

## Dicionário: `demonstracoes`
| Coluna | Tipo | Descrição |
|---|---|---|
| cd_cvm | int | código da companhia |
| tipo_doc | text | `DFP` ou `ITR` |
| demonstracao | text | `DRE`, `BPA`, `BPP`, … |
| consolidacao | text | `con` consolidado / `ind` individual |
| dt_refer | date | data-base |
| dt_ini_exerc / dt_fim_exerc | date | período (DRE/DFC; nulo em balanços) |
| cd_conta / ds_conta | text | código hierárquico (ex.: `3.01`) e descrição |
| vl_conta | numeric | valor **em reais** |

Contas úteis: DRE `3.01` receita, `3.05` resultado antes de financeiro e tributos (EBIT), `3.11` lucro/prejuízo consolidado do período · BPA `1` ativo total · BPP `2.03` patrimônio líquido.

## Armadilhas
1. **Bancos/seguradoras** têm plano de contas diferente: `3.01` não é "receita de vendas". O benchmark inclui isso de propósito; para análise séria, normalize por setor.
2. **ITR**: a DRE traz linhas do trimestre **e** do acumulado no ano (`DT_INI_EXERC` distingue). Cada um vira um cartão distinto.
3. **Lucro por ação (`3.99.*`)** está em R$/ação, não na escala do demonstrativo ⇒ excluído dos cartões (`SKIP_PREFIXES`).
4. **Ordenação de contas**: `3.10 < 3.2` em texto; cartões ordenam numericamente por segmento.
5. **Empresas com nomes parecidos** (VALE × VALE DO RIO…): `--empresa` resolve por alias e aborta se ambíguo.
6. **Encoding**: latin-1 nos CSV; mojibake indica encoding errado.
7. **IPE**: o link do documento pode devolver PDF, HTML ou ZIP; ZIP e conteúdos sem texto ficam `ignorado`. PDFs escaneados exigiriam OCR (não incluído).
8. **Look-ahead bias** (para backtests futuros): `dt_refer` ≠ data de divulgação. Para uso point-in-time, registre a data de entrega (disponível no IPE/`DT_RECEB` em arquivos gerais).
