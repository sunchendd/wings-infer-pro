# G.EXP.06 代码中不应使用断言（assert）

- **规则ID**：0225b7ed-273e-40f3-9680-3bb7e8786d6d
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

一般

**【描述】**

使用assert断言语是对代码进行诊断测试的方便机制。当使用有副作用的断言表达式时，assert语句的行为取决于运行时属性的状态，启用时，assert语句会计算表达式的值，如果值为false时抛出AssertionError异常；禁用时，assert语句不执行

**【正确示例】**

```
public void process01Good(List<String> names) {
    assert names != null;
    // ...
}

```
**【错误示例】**

```
public void processBad() {
    boolean check;
    /* POTENTIAL FLAW: Expressions used in assertions must not produce side effects,which means the expressions should avoid altering or modifying the value of Objects or variables. */
    assert check = true;
    // ...
}

```
**【修复建议】**

不要在断言中使用有副作用的表达式
