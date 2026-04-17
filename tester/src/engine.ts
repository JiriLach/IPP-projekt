// src/engine.ts
/*
 * Engine module for the SOL tester.
 * Author: Jiří Lach <xlachji00@stud.fit.vut.cz>
 */
import {
  existsSync,
  readdirSync,
  readFileSync,
  writeFileSync,
  rmSync,
  mkdtempSync,
} from "node:fs";
import { dirname, join, basename } from "node:path";
import { spawnSync } from "node:child_process";
import * as os from "node:os";

import {
  TestCaseDefinition,
  TestCaseType,
  TestCaseDefinitionInit,
  UnexecutedReason,
  UnexecutedReasonCode,
  TestCaseReport,
  TestResult,
} from "./models.js";

export interface FilterConfig {
  regex_filters?: boolean;
  include?: string[] | null;
  include_category?: string[] | null;
  include_test?: string[] | null;
  exclude?: string[] | null;
  exclude_category?: string[] | null;
  exclude_test?: string[] | null;
}

const PARSER_CMD = process.env["SOL2XML"] || "sol2xml";
const INTERPRETER_CMD = process.env["SOLINT"] || "python3 ./int/src/solint.py";

export class InternalTestCaseDefinition extends TestCaseDefinition {
  public readonly sourceCode: string;
  constructor(init: TestCaseDefinitionInit, sourceCode: string) {
    super(init);
    this.sourceCode = sourceCode;
  }
}

export function findTestFiles(dir: string, recursive: boolean): string[] {
  let results: string[] = [];
  const entries = readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory() && recursive)
      results = results.concat(findTestFiles(fullPath, recursive));
    else if (entry.isFile() && entry.name.endsWith(".test")) results.push(fullPath);
  }
  return results;
}



interface ParsedHeader {
  description: string | null;
  category: string;
  points: number;
  expC: number[];
  expI: number[];
  codeStartIndex: number;
}

function parseHeader(lines: string[]): ParsedHeader {
  let description: string | null = null,
    category = "",
    points = 1;
  const expC: number[] = [];
  const expI: number[] = [];
  let i = 0;

  for (; i < lines.length; i++) {
    const rawLine = lines[i];
    if (rawLine === undefined) break;

    const line = rawLine.trim();
    if (line === "") {
      i++;
      break;
    }

    if (line.startsWith("***")) description = line.substring(3).trim();
    else if (line.startsWith("+++")) category = line.substring(3).trim();
    else if (line.startsWith("!C!")) expC.push(parseInt(line.substring(3).trim(), 10));
    else if (line.startsWith("!I!")) expI.push(parseInt(line.substring(3).trim(), 10));
    else if (line.startsWith(">>>")) points = parseInt(line.substring(3).trim(), 10);
  }

  return { description, category, points, expC, expI, codeStartIndex: i };
}

function determineTestType(
  sourceCode: string,
  expC: number[],
  expI: number[]
): TestCaseType | null {
  if (sourceCode.startsWith("<?xml") || sourceCode.startsWith("<program"))
    return TestCaseType.EXECUTE_ONLY;
  if (expC.length > 0 && expI.length === 0) return TestCaseType.PARSE_ONLY;
  if (expC.length > 0 && expI.length > 0) return TestCaseType.COMBINED;
  if (expC.length === 0 && expI.length > 0) return TestCaseType.EXECUTE_ONLY;
  return null;
}


export function parseTestFile(
  testFilePath: string
): InternalTestCaseDefinition | UnexecutedReason {
  try {
    const content = readFileSync(testFilePath, "utf8");
    const lines = content.split(/\r?\n/);

    const header = parseHeader(lines);
    const sourceCode = lines.slice(header.codeStartIndex).join("\n").trim();
    const testName = basename(testFilePath, ".test");
    const testDir = dirname(testFilePath);

    const stdinFile = join(testDir, `${testName}.in`);
    const stdoutFile = join(testDir, `${testName}.out`);

    const testType = determineTestType(sourceCode, header.expC, header.expI);
    if (testType === null) {
      return new UnexecutedReason(
        UnexecutedReasonCode.CANNOT_DETERMINE_TYPE,
        "Nelze určit typ testu (!C! a !I! chybí)."
      );
    }

    return new InternalTestCaseDefinition(
      {
        name: testName,
        test_source_path: testFilePath,
        stdin_file: existsSync(stdinFile) ? stdinFile : null,
        expected_stdout_file: existsSync(stdoutFile) ? stdoutFile : null,
        test_type: testType,
        description: header.description,
        category: header.category,
        points: header.points,
        expected_parser_exit_codes: header.expC.length > 0 ? header.expC : null,
        expected_interpreter_exit_codes: header.expI.length > 0 ? header.expI : null,
      },
      sourceCode
    );
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return new UnexecutedReason(UnexecutedReasonCode.MALFORMED_TEST_CASE_FILE, msg);
  }
}

export function filterTestCases(tests: InternalTestCaseDefinition[], args: FilterConfig) {
  const toRun: InternalTestCaseDefinition[] = [],
    filteredOut: InternalTestCaseDefinition[] = [];

  const isMatch = (val: string, crit: string[] | null | undefined) => {
    if (!crit) return false;
    return crit.some((c) => (args.regex_filters ? new RegExp(c).test(val) : val === c));
  };

  for (const test of tests) {
    let inc = !(args.include || args.include_category || args.include_test);
    if (!inc) {
      if (isMatch(test.name, args.include) || isMatch(test.category, args.include)) inc = true;
      if (isMatch(test.category, args.include_category)) inc = true;
      if (isMatch(test.name, args.include_test)) inc = true;
    }

    let exc = false;
    if (isMatch(test.name, args.exclude) || isMatch(test.category, args.exclude)) exc = true;
    if (isMatch(test.category, args.exclude_category)) exc = true;
    if (isMatch(test.name, args.exclude_test)) exc = true;

    if (inc && !exc) toRun.push(test);
    else filteredOut.push(test);
  }
  return { toRun, filteredOut };
}

function runParserCmd(sourceCode: string): { rc: number; out: string; err: string } {
  const pRes = spawnSync(PARSER_CMD, [], { input: sourceCode, shell: true, encoding: "utf8" });
  return { rc: pRes.status ?? 0, out: pRes.stdout || "", err: pRes.stderr || "" };
}

function runInterpreterCmd(
  pathToExecute: string,
  stdinFile: string | null
): { rc: number; out: string; err: string } {
  const inputData = stdinFile ? readFileSync(stdinFile, "utf8") : "";
  const iRes = spawnSync(`${INTERPRETER_CMD} -s ${pathToExecute}`, [], {
    input: inputData,
    shell: true,
    encoding: "utf8",
  });
  return { rc: iRes.status ?? 0, out: iRes.stdout || "", err: iRes.stderr || "" };
}

export function executeTest(test: InternalTestCaseDefinition): TestCaseReport {
  let parseRc: number | null = null,
    intRc: number | null = null;
  let pOut = "",
    pErr = "",
    iOut = "",
    iErr = "";

  const tmpDir = mkdtempSync(join(os.tmpdir(), "soltest-"));
  const srcFile = join(tmpDir, "source.tmp"),
    xmlFile = join(tmpDir, "parsed.xml");
  writeFileSync(srcFile, test.sourceCode, "utf8");

  try {
    let pathToExecute = srcFile;

    // 1. phase: Parse
    if (test.test_type === TestCaseType.PARSE_ONLY || test.test_type === TestCaseType.COMBINED) {
      const pRes = runParserCmd(test.sourceCode);
      parseRc = pRes.rc;
      pOut = pRes.out;
      pErr = pRes.err;

      writeFileSync(xmlFile, pOut, "utf8");
      pathToExecute = xmlFile;

      if (!test.expected_parser_exit_codes?.includes(parseRc)) {
        return new TestCaseReport(
          TestResult.UNEXPECTED_PARSER_EXIT_CODE,
          parseRc,
          null,
          pOut,
          pErr,
          null,
          null,
          null
        );
      }
      if (test.test_type === TestCaseType.PARSE_ONLY) {
        return new TestCaseReport(TestResult.PASSED, parseRc, null, pOut, pErr, null, null, null);
      }
    }

    // 2. phase: Interpret
    const iRes = runInterpreterCmd(pathToExecute, test.stdin_file);
    intRc = iRes.rc;
    iOut = iRes.out;
    iErr = iRes.err;

    if (!test.expected_interpreter_exit_codes?.includes(intRc)) {
      return new TestCaseReport(
        TestResult.UNEXPECTED_INTERPRETER_EXIT_CODE,
        parseRc,
        intRc,
        pOut,
        pErr,
        iOut,
        iErr,
        null
      );
    }

    // 3. phase: Diff
    if (intRc === 0 && test.expected_stdout_file) {
      const actOutFile = join(tmpDir, "actual.out");
      writeFileSync(actOutFile, iOut, "utf8");

      const diffRes = spawnSync("diff", [test.expected_stdout_file, actOutFile], {
        encoding: "utf8",
      });
      if (diffRes.status !== 0) {
        return new TestCaseReport(
          TestResult.INTERPRETER_RESULT_DIFFERS,
          parseRc,
          intRc,
          pOut,
          pErr,
          iOut,
          iErr,
          diffRes.stdout || ""
        );
      }
    }

    return new TestCaseReport(TestResult.PASSED, parseRc, intRc, pOut, pErr, iOut, iErr, null);
  } finally {
    rmSync(tmpDir, { recursive: true, force: true });
  }
}
