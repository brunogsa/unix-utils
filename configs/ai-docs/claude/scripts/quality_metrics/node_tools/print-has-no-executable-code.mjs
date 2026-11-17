#!/usr/bin/env node
// print-has-no-executable-code.mjs - Tell whether a JS/TS
// file holds no executable code.
//
// Usage:
//   print-has-no-executable-code.mjs <file>
//
// stdin: unused.
//
// stdout: "true" when every top-level statement is an import,
// a re-export, a type-only export, a type alias or an
// interface; "false" otherwise.
//
// An empty file, or one that does not parse, prints "false".
//
// exit: 0 on an answer, 1 when the file cannot be read.

import { readFileSync } from 'node:fs';
import ts from 'typescript';

const SCRIPT_KIND_BY_EXTENSION = {
  '.ts': ts.ScriptKind.TS, '.mts': ts.ScriptKind.TS, '.cts': ts.ScriptKind.TS,
  '.tsx': ts.ScriptKind.TSX, '.jsx': ts.ScriptKind.JSX,
  '.js': ts.ScriptKind.JS, '.mjs': ts.ScriptKind.JS, '.cjs': ts.ScriptKind.JS,
};

// An export with no `from` runs code unless it names only
// types.
function isTypeOnlyLocalExport(statement) {
  if (statement.isTypeOnly) {
    return true;
  }
  const clause = statement.exportClause;
  const isNamedExports = clause !== undefined && ts.isNamedExports(clause);
  return isNamedExports && clause.elements.length > 0 && clause.elements.every((element) => element.isTypeOnly);
}

function isWithoutExecutableCode(statement) {
  if (ts.isImportDeclaration(statement)) {
    return true;
  }
  if (ts.isExportDeclaration(statement)) {
    return statement.moduleSpecifier !== undefined || isTypeOnlyLocalExport(statement);
  }
  return ts.isTypeAliasDeclaration(statement) || ts.isInterfaceDeclaration(statement);
}

function hasNoExecutableCode(path, text) {
  const extension = path.slice(path.lastIndexOf('.'));
  const scriptKind = SCRIPT_KIND_BY_EXTENSION[extension];
  if (scriptKind === undefined) {
    return false;
  }
  const sourceFile = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, false, scriptKind);

  // A file that does not parse cannot be judged, so it keeps
  // its measured reading.
  if (sourceFile.parseDiagnostics.length > 0) {
    return false;
  }
  const { statements } = sourceFile;
  return statements.length > 0 && statements.every(isWithoutExecutableCode);
}

const [path] = process.argv.slice(2);
if (path === undefined) {
  console.error('usage: print-has-no-executable-code.mjs <file>');
  process.exit(1);
}
let text;
try {
  text = readFileSync(path, 'utf8');
} catch (error) {
  console.error(`cannot read ${path}: ${error.message}`);
  process.exit(1);
}
console.log(String(hasNoExecutableCode(path, text)));
