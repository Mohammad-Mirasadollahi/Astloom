"""Multi-language parser and ingest coverage (Python, TS, JS, Go, Rust)."""

from __future__ import annotations

from code_graph_service.core import CodeGraphService, Scope, detect_language_from_path, parse_source
from code_graph_service.domain.parsers import registered_parsers
from code_graph_service.testing import InMemoryStore

SCOPE = Scope("t", "w", "polyglot")

JS_SOURCE = """
import { helper as helpFn } from "./helpers";
class Auth {
  login(user, password) { return this.check(password); }
  check(password) { return password.length > 8; }
}
function top() { return helpFn(1); }
"""

TS_SOURCE = """
import { helper as helpFn } from "./helpers";
export class Auth {
  login(user: string, password: string): boolean { return this.check(password); }
  check(password: string): boolean { return password.length > 8; }
}
export function top(): number { return helpFn(1); }
"""

GO_SOURCE = """
package auth

import "fmt"

type User struct { Name string }

func CheckPassword(password string) bool { return len(password) > 8 }

func Login(user string, password string) bool { return CheckPassword(password) }

func (u *User) Greet() { fmt.Println(u.Name) }
"""

RUST_SOURCE = """
use std::collections::HashMap;

struct Auth {}

impl Auth {
    fn check_password(password: &str) -> bool { password.len() > 8 }
    fn login(&self, password: &str) -> bool { Self::check_password(password) }
}

fn top() -> bool { Auth::check_password("x") }
"""


def test_registered_parsers_include_rust_and_matrix_langs():
    assert set(registered_parsers()) == {
        "python",
        "javascript",
        "typescript",
        "go",
        "rust",
        "java",
    }
    assert detect_language_from_path("pkg/main.rs") == "rust"
    assert detect_language_from_path("src/app.tsx") == "typescript"
    assert detect_language_from_path("lib/util.go") == "go"
    assert detect_language_from_path("src/main/java/App.java") == "java"


JAVA_SOURCE = """
package com.acme.auth;

import com.acme.util.Helper;

public class Auth {
  public boolean login(String password) { return check(password); }
  public boolean check(String password) { return password.length() > 8; }
}
"""


def test_parse_javascript_typescript_go_rust_symbols():
    js = parse_source("javascript", "src/auth.js", JS_SOURCE)
    assert any(s.qualified_name.endswith(".Auth.login") for s in js.symbols)
    assert "helpFn" in js.import_aliases

    ts = parse_source("typescript", "src/auth.ts", TS_SOURCE)
    assert any(s.kind.value == "method" and s.name == "check" for s in ts.symbols)

    go = parse_source("go", "auth.go", GO_SOURCE)
    assert any(s.qualified_name == "auth.Login" for s in go.symbols)
    assert any(s.qualified_name == "auth.User.Greet" for s in go.symbols)

    rust = parse_source("rust", "src/auth.rs", RUST_SOURCE)
    assert any(s.name == "check_password" for s in rust.symbols)
    assert any(s.name == "top" for s in rust.symbols)

    java = parse_source("java", "Auth.java", JAVA_SOURCE)
    assert any(s.name == "Auth" and s.kind.value == "class" for s in java.symbols)
    assert any(s.name == "login" for s in java.symbols)
    assert "Helper" in java.import_aliases


def test_ingest_polyglot_project_builds_edges_per_language():
    store = InMemoryStore()
    service = CodeGraphService(store)

    service.ingest_file(
        SCOPE, "agent", "c1", "idem-js",
        {"file_path": "src/auth.js", "source": JS_SOURCE, "language": "javascript"},
    )
    service.ingest_file(
        SCOPE, "agent", "c2", "idem-ts",
        {"file_path": "src/auth.ts", "source": TS_SOURCE, "language": "typescript"},
    )
    service.ingest_file(
        SCOPE, "agent", "c3", "idem-go",
        {"file_path": "auth.go", "source": GO_SOURCE, "language": "go"},
    )
    rust = service.ingest_file(
        SCOPE, "agent", "c4", "idem-rs",
        {"file_path": "src/auth.rs", "source": RUST_SOURCE, "language": "rust"},
    )
    assert rust.symbols_indexed >= 3

    login_js = f"sym:{SCOPE.project_id}:src.auth.Auth.login"
    neighbors = service.structural_query(SCOPE, login_js, "CALLS")
    assert any(edge["rel_type"] == "CALLS" for edge in neighbors["edges"])

    go_login = f"sym:{SCOPE.project_id}:auth.Login"
    go_neighbors = service.structural_query(SCOPE, go_login, "CALLS")
    assert any(edge["rel_type"] == "CALLS" for edge in go_neighbors["edges"])
