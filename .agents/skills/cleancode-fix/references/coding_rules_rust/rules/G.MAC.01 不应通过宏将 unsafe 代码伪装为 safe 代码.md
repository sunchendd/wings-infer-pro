# G.MAC.01 不应通过宏将 unsafe 代码伪装为 safe 代码

- **规则ID**：51c64997-3781-4146-b44f-bdbff2089f35
- **更新时间**：2026-04-07 04:40:01

---

**【问题级别】**

一般

**【描述】**

不应通过过程宏将 unsafe 代码包装为 safe 代码

**【正确示例】**

```
```
#[proc_macro]
pub fn rprintf(input: TokenStream) -> TokenStream {
    let expr = parse_macro_input!(input as syn::Expr);
    quote!({
        // unsafe operation
    })
}
```

```
**【错误示例】**

```
```
#[proc_macro]
pub fn rprintf(input: TokenStream) -> TokenStream {
    let expr = parse_macro_input!(input as syn::Expr);
    quote!({
        unsafe {
            // unsafe operation
        }
    })
}
```

```
**【修复建议】**

不应通过过程宏将 unsafe 代码包装为 safe 代码
