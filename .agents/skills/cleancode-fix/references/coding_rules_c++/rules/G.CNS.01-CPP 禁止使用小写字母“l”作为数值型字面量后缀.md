# G.CNS.01-CPP 禁止使用小写字母“l”作为数值型字面量后缀

- **规则ID**：df16b7f9-28af-4deb-bf94-0cbc4adb0a37
- **更新时间**：2025-03-25 19:22:13

---

**【问题级别】**

严重

**【描述】**

C++标准允许使用后缀来显式指定数值型字面量的类型，例如：整数字面量可以使用后缀字母 l 或 L 表示long类型，使用字母 ll 或 LL 表示 long long类型。

当使用小写字母 l 指定数值型字面量类型时，在视觉上容易和数字 1 混淆。为了避免这种混淆带来的误解，应使用大写字母 L 或 LL 作为数值型字面量的后缀。

**【正确示例】**

```
constexpr long long BARRETT_REDUCTION = 0xFF6511LL;
constexpr long double MAX_DEGREE = 180.0L;

```
**【错误示例】**

```
constexpr long long BARRETT_REDUCTION = 0xFF6511ll;
constexpr long double MAX_DEGREE = 180.0l;

```
**【修复建议】**

小写"l"替换成大写"L"
