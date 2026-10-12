# G.CAR.02 Crate 的 Cargo.toml 中应该包含必要的元信息-试行

- **规则ID**：7f1e54df-c792-4693-bb76-2c0eda1414be
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

在 Cargo.toml 中应该包含必要的元信息，以便使用者知道它的作用。

**【正确示例】**

```
# 此 `Cargo.toml` 包含必要元信息。
[package]
name = "clippy"
version = "0.0.212"
description = "A bunch of helpful lints to avoid common pitfalls in Rust"
repository = "https://github.com/rust-lang/rust-clippy"
readme = "README.md"
license = "MIT OR Apache-2.0"
keywords = ["clippy", "lint", "plugin"]
categories = ["development-tools", "development-tools::cargo-plugins"]

```
**【错误示例】**

```
# 此 `Cargo.toml` 缺失介绍(description)项。无法发布到 crates.io。
[package]
name = "clippy"
version = "0.0.212"
repository = "https://github.com/rust-lang/rust-clippy"
readme = "README.md"
license = "MIT OR Apache-2.0"
keywords = ["clippy", "lint", "plugin"]
categories = ["development-tools", "development-tools::cargo-plugins"]

```
**【修复建议】**
