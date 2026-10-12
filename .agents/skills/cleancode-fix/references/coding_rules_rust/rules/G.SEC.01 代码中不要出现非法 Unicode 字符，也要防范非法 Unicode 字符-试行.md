# G.SEC.01 代码中不要出现非法 Unicode 字符，也要防范非法 Unicode 字符-试行

- **规则ID**：efd0d742-131a-470b-9738-3bea34235356
- **更新时间**：2025-06-05 04:40:04

---

**【问题级别】**

严重

**【描述】**

非法 Unicode 字符可能引起安全问题。安全问题参见： Rust 编译器安全公告（CVE-2021-42574）



禁止的 Unicode 字符类别为：



隐藏的 Unicode 字符

双向 Unicode 字符文本

同形 Unicode 字符

Clippy Lint 目前只可以检测代码中出现的隐藏 Unicode 字符。



在 Rust 1.56.1 之后 新增两个 lint 拒绝代码中出现可以更改显示顺序的 Unicode 码点出现。并且特别禁止 \u{202A}，\u{202B}，\u{202D}，\u{202E}，\u{2066}， \u{2067}，\u{2068}，\u{202C}和\u{2069} 这几个特殊的 Unicode 码点。



Rust 的 mixed_script_confusables 和 confusable_idents 可以识别 同形字符。



写代码的时候需要注意，尤其是开源代码，需要防范上述非法 Unicode 字符。

**【正确示例】**

```
#![deny(text_direction_codepoint_in_comment)]
// 这段代码不应该输出里面的打印语句，但实际上输出了。
// 因为开发者看上去条件表达式里 确实等于 "user"，但实际上不等于"user"，因为这个字符串里被加了隐藏字符。
fn main() {
    let access_level = "user";
    if access_level != "user‮ ⁦// Check if admin⁩ ⁦" {
        println!("You are an admin.");
    }
}
#![deny(text_direction_codepoint_in_literal)]
// 该文件包含双向Unicode文本，其解释或编译方式可能与下面的内容不同。要审查，请在一个能显示隐藏的Unicode字符的编辑器中打开该文件。
// 执行输出 
fn main() {
    let is_admin = false;
    /*‮ } ⁦if is_admin⁩ ⁦ begin admins only */
        println!("You are an admin.");
    /* end admins only ‮ { ⁦*/
}

```
**【错误示例】**

```


```
**【修复建议】**
