# G.MUSIC.4 使用MathUtils 替换原生的Integer.parseInt Long.parseLong Double.parseDouble Float.parseFloat Short.parseShort Long.decode Integer.decode Short.decode Integer.valueOf Long.valueOf Double.valueOf Float.valueOf Short.valueOf等不安全的数字转换方法

- **规则ID**：3518715e-4303-443b-b6ae-c6f2f7ae040a
- **更新时间**：2025-06-05 04:00:06

---

**【问题级别】**

一般

**【描述】**

使用项目工程中已经封装的工具类MathUtils

**【正确示例】**

```
private void foo(String s){

    int v = MathUtils.parseInt(s, 0);

}

```
**【错误示例】**

```
private void foo(String s) {

    int v = Integer.parseInt(s);

}

```
**【修复建议】**

使用安全的数字转换方法
