#!/usr/bin/env bash
# test-check-pr-template-headings.sh - plain-bash test file for
# check-pr-template-headings.sh.
#
# Usage:
#   bash test-check-pr-template-headings.sh
#
# Exits 0 when every assertion passes, non-zero otherwise.
# No bats dependency by design, matching the other scripts in
# this skill's test suite.

set -uo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$script_dir/check-pr-template-headings.sh"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

pass_count=0
fail_count=0

# assert_eq - inline assert helper: compares expected vs actual,
# prints ok/not-ok.
assert_eq() {
  local description="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    pass_count=$((pass_count + 1))
    printf 'ok - %s\n' "$description"
  else
    fail_count=$((fail_count + 1))
    printf 'not ok - %s\n  expected: %s\n  actual:   %s\n' "$description" "$expected" "$actual"
  fi
}

# run_script - invokes check-pr-template-headings.sh with any
# number of args, capturing the exit code into VERDICT_EXIT and
# stderr into VERDICT_ERR: the failing heading is named there.
run_script() {
  local out_file="$work_dir/stdout.txt"
  local err_file="$work_dir/stderr.txt"
  VERDICT_EXIT=0
  bash "$SCRIPT" "$@" >"$out_file" 2>"$err_file" || VERDICT_EXIT=$?
  VERDICT_ERR=$(cat "$err_file")
}

# write_md - writes the given markdown to a fresh fixture under
# work_dir, returns its path via stdout.
write_md() {
  local name="$1" content="$2"
  local path="$work_dir/$name.md"
  printf '%s\n' "$content" > "$path"
  printf '%s' "$path"
}

# Shaped after a real repo template (arco2-integrator's
# .github/PULL_REQUEST_TEMPLATE.md): it mixes ### and ####
# headings and carries HTML-comment placeholders.
TEMPLATE='### Link do Linear

- [CDPI-XXX](https://linear.app/isaac/issue/CDPI-XXX/)

### Contexto do PR

<!--
Use esse espaço para explicar brevemente aos revisores o que eles precisam saber
-->

#### Lista do que foi feito:

#### Sobre a solução

### Checklist

- [ ] Foi testado localmente

### Imagens, PrintScreens, vídeos

### Referências: artigos, documentação'

it_should_pass_a_body_holding_every_template_heading_in_order_with_extra_headings_between() {
  local template body
  template=$(write_md "template" "$TEMPLATE")
  body=$(write_md "body-in-order" '### Link do Linear

- [CDPI-1042](https://linear.app/isaac/issue/CDPI-1042/)

### Contexto do PR

Adds a dependency failures alarm.

#### Lista do que foi feito:

- Adds the alarm

#### Sobre a solução

##### Funcionais

##### Técnicas

### Checklist

- [x] Foi testado localmente

### Evidências

12 tests added.

### Imagens, PrintScreens, vídeos

### Referências: artigos, documentação

## Apêndice - leitura opcional

### Technical Decisions')
  run_script "$body" "$template"
  assert_eq "should pass a body holding every template heading in template order, with extra headings between them (exit code)" "0" "$VERDICT_EXIT"
}

it_should_fail_a_body_missing_one_template_heading_and_name_it() {
  local template body
  template=$(write_md "template" "$TEMPLATE")
  body=$(write_md "body-missing" '### Link do Linear

### Contexto do PR

#### Lista do que foi feito:

### Checklist

### Imagens, PrintScreens, vídeos

### Referências: artigos, documentação')
  run_script "$body" "$template"
  assert_eq "should fail a body missing one template heading (exit code)" "1" "$VERDICT_EXIT"
  assert_eq "should name the missing template heading on stderr" "1" "$(printf '%s\n' "$VERDICT_ERR" | grep -c 'missing.*#### Sobre a solução')"
}

it_should_fail_a_body_with_template_headings_out_of_order_and_name_the_first_misplaced_one() {
  local template body
  template=$(write_md "template" "$TEMPLATE")
  body=$(write_md "body-out-of-order" '### Link do Linear

### Contexto do PR

#### Lista do que foi feito:

#### Sobre a solução

### Imagens, PrintScreens, vídeos

### Checklist

### Referências: artigos, documentação')
  run_script "$body" "$template"
  assert_eq "should fail a body holding every template heading but out of template order (exit code)" "1" "$VERDICT_EXIT"
  assert_eq "should name the first template heading found out of order on stderr" "1" "$(printf '%s\n' "$VERDICT_ERR" | grep -c 'out of order.*### Imagens, PrintScreens, vídeos')"
}

it_should_not_require_a_heading_that_sits_inside_a_fenced_code_block_of_the_template() {
  local template body
  template=$(write_md "template-with-fence" '### Link do Linear

```markdown
### Exemplo de seção
```

### Checklist')
  body=$(write_md "body-without-fenced-heading" '### Link do Linear

### Checklist')
  run_script "$body" "$template"
  assert_eq "should not require a heading that sits inside a fenced code block of the template (exit code)" "0" "$VERDICT_EXIT"
}

it_should_not_count_a_template_heading_that_appears_only_inside_a_fenced_code_block_of_the_body() {
  local template body
  template=$(write_md "template-two-headings" '### Link do Linear

### Checklist')
  body=$(write_md "body-heading-only-in-fence" '### Link do Linear

```markdown
### Checklist
```')
  run_script "$body" "$template"
  assert_eq "should fail a body whose only copy of a template heading sits inside a fenced code block (exit code)" "1" "$VERDICT_EXIT"
  assert_eq "should name the heading found only inside a fence as missing on stderr" "1" "$(printf '%s\n' "$VERDICT_ERR" | grep -c 'missing.*### Checklist')"
}

it_should_exit_2_when_the_body_file_does_not_exist() {
  local template
  template=$(write_md "template" "$TEMPLATE")
  run_script "$work_dir/does-not-exist.md" "$template"
  assert_eq "should exit 2 when the body file does not exist" "2" "$VERDICT_EXIT"
}

it_should_exit_2_when_called_without_the_template_argument() {
  local body
  body=$(write_md "body-alone" '### Link do Linear')
  run_script "$body"
  assert_eq "should exit 2 when called without the template argument" "2" "$VERDICT_EXIT"
}

it_should_pass_a_body_holding_every_template_heading_in_order_with_extra_headings_between
it_should_fail_a_body_missing_one_template_heading_and_name_it
it_should_fail_a_body_with_template_headings_out_of_order_and_name_the_first_misplaced_one
it_should_not_require_a_heading_that_sits_inside_a_fenced_code_block_of_the_template
it_should_not_count_a_template_heading_that_appears_only_inside_a_fenced_code_block_of_the_body
it_should_exit_2_when_the_body_file_does_not_exist
it_should_exit_2_when_called_without_the_template_argument

printf '\n%d passed, %d failed\n' "$pass_count" "$fail_count"
[ "$fail_count" -eq 0 ]
