# G.TYP.05 浮点型数据判断相等不要直接使用==，浮点型包装类型不要用equals()或者 flt.compareTo(another) == 0作相等的比较

- **规则ID**：9bd37aa6-fb9d-47f2-91d8-edc4c7d2d649
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

严重

**【描述】**

浮点型数据判断相等不要直接使用==，浮点型包装类型不要用equals()或者 flt.compareTo(another) == 0作相等的比较



2021年4月8日：新增两个浮点变量==比较的场景



工具检查场景:

- 检查浮点型数据使用==、!=来判断相等。

- 检查浮点型数据使用equals或compareTo来判断相等

**【正确示例】**

```
考虑浮点数的精度问题，可在一定的误差范围内判定两个浮点数值相等。这个误差应根据实际需要进行定义。另外，对于符号不同的两个浮点数，即使在误差范围内也不应该判为相等。如下示例中，两个浮点数值误差在1e-6f内判为相等。
private static final float EPSILON = e-f;

float foo = ...;
float bar = ...;
if (Math.abs(foo - bar) < EPSILON) {
    ...
}

```
**【错误示例】**

```
float f1 = 1.0f - 0.9f;
float f2 = 0.9f - 0.8f;
if (f1 == f2) {
    // 预期进入此代码块，执行其他业务逻辑
    // 但事实上 fl == f2 的结果为 false
}
Float flt1 = Float.valueOf(f1);
Float flt2 = Float.valueOf(f2);
if (flt1.equals(flt2)) {
    // 预期进入此代码块，执行其他业务逻辑
    // 但事实上 equals 的结果为 false
}

```
**【修复建议】**

使用误差判等
