# G.CMT.03 方法的Javadoc中应该包含功能说明，根据实际需要按顺序使用@param、@return、@throws标签对参数、返回值、异常进行注释

- **规则ID**：2e543c7e-206a-48e4-b51a-7ecc79aed099
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

方法的Javadoc中应该包含功能说明，根据实际需要按顺序使用@param、@return、@throws标签对参数、返回值、异常进行注释



工具检查场景:

- 检查方法的Javadoc是否有功能说明；如果没有Javadoc，这条规则不告警，会在G.CMT.01中告警

- 检查方法的Javadoc的功能描述与标签之间是否只空1行，没有空行和多余空行都会告警

- 如果方法有参数，检查Javadoc中是否对每个参数都有@param标签

- 如果方法有返回值，检查Javadoc中是否有@return标签

- 如果方法有抛异常，检查Javadoc中是否对每个异常都有@throws标签

- 检查标签是否按照@param、@return、@throws的顺序排列

- 检查Javadoc第一行或最后一行不能有注释内容

- 例外场景：

  - 不检查继承的Javadoc（ @inheritDoc）

  - 不检查隐藏的Javadoc（@hide）

**【正确示例】**

```
/**
 * 对示例接口的概述介绍
 *
 * @since 2019-01-01
 */
protected abstract class Sample {
    /**
     * 这是一段长注释，要根据注释内容进行合理拆分为多行注释...
     * 这是第二行注释。
     * 符合： 功能说明要与下面的@标签之间保留一个空行
     *
     * @param fox 参数fox的说明，例如：与懒狗进行挑战的狐狸对象
     * @return 方法返回值的说明，例如：返回狐狸与狗的交战结果
     */
    protected abstract int foo(Fox fox);

    /**
     * 函数的功能说明
     * 符合： 功能说明要与下面的@标签之间保留一个空行
     *
     * @return 方法返回值的说明，例如：返回狐狸与狗的交战结果
     * @throws ProblemException 异常说明，例如：懒狗死亡抛出该异常
     */
    protected int bar() throws ProblemException {
        // 变量注释
        var aVar = ...;

        // 方法注释  符合：注释要与前面的代码之间保留一个空行
        doSome();
    }
}

```
**【错误示例】**

```
    /**
     */
    public void methodDemo() {
    }

```
**【修复建议】**

增加功能说明和相应标签
