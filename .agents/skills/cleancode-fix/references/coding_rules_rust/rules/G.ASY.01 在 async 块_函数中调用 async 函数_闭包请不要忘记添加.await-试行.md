# G.ASY.01 在 async 块/函数中调用 async 函数/闭包请不要忘记添加.await-试行

- **规则ID**：2ff7a0d3-dea2-46ee-b933-730ba6d30bfc
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

严重

**【描述】**



**【正确示例】**

```
async fn foo() {}
fn bar() {
  let x = async {
    foo().await
  };
}

```
**【错误示例】**

```
async fn foo() {}
fn bar() {
  let x = async {
    foo()
  };
}

```
**【修复建议】**
