# G.FUD.03 当函数参数出现太多 bool 类型的参数时，应该考虑将其封装为自定义的结构体或枚举-试行

- **规则ID**：78bd3da3-3799-4d39-a4f9-6e324bdcddc7
- **更新时间**：2025-06-05 04:40:03

---

**【问题级别】**

提示

**【描述】**

布尔类型的参数过多，很难让人记住，容易出错。将其封装为枚举或结构体，可以更好地利用类型系统的检查而避免出错。



其他类型参数过多时，也可以考虑是否可以用自定义结构体或枚举进行封装。

**【正确示例】**

```
enum Shape {
    Round,
    Spiky,
}
enum Temperature {
    Hot,
    IceCold,
}
fn f(shape: Shape, temperature: Temperature) { ... }

```
**【错误示例】**

```
fn f(is_round: bool, is_hot: bool) { ... }

```
**【修复建议】**
