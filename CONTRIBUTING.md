# Fluxo de desenvolvimento

Toda alteração deve partir da branch `18.0` e entrar nela por pull request.
Commits funcionais diretos na `18.0` não fazem parte do fluxo do projeto.

## Criar uma branch

Com a árvore de trabalho limpa, execute:

```bash
python3 scripts/start_branch.py feature nome-da-funcionalidade
```

Tipos aceitos:

- `feature`: funcionalidade nova;
- `fix`: correção de defeito;
- `refactor`: reorganização sem mudança funcional;
- `docs`: documentação;
- `chore`: manutenção, automação ou infraestrutura.

O nome gerado segue o padrão `18.0-TIPO-DESCRICAO`, por exemplo:

```text
18.0-feature-dynamic-tax-preview
18.0-fix-profit-calculation
18.0-chore-development-workflow
```

## Registrar a alteração

Antes de abrir a PR, adicione um resumo ao changelog:

```bash
python3 scripts/add_changelog.py added "Descrição curta da funcionalidade"
```

Categorias aceitas: `added`, `changed`, `fixed` e `removed`.

## Pull request

Uma PR deve conter somente um assunto, explicar como foi validada e atualizar
o `CHANGELOG.md`. O GitHub valida automaticamente o nome da branch e a presença
do changelog.
