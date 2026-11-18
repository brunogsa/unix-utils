# Wraps the stamped guide in the collapsed comment body.
# Inputs: --rawfile guide, --arg sha (7 characters), --arg at.
{body: ("<details>\n<summary><strong>Guia de review</strong> · commit <code>" + $sha + "</code> · " + $at + "</summary>\n\n" + ($guide | rtrimstr("\n")) + "\n\n</details>\n\ngerado por IA")}
