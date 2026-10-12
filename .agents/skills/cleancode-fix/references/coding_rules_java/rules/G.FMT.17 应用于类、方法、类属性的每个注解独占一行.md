# G.FMT.17 应用于类、方法、类属性的每个注解独占一行

- **规则ID**：d2db0116-7282-4608-8c0d-ebe91a0dd853
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

应用于类、方法（含构造方法）、类属性的注解应在其上部，且每个注解独占一行。

**【正确示例】**

```
##### 场景1：多个注解共处一行
- 修复示例1：每个注解独占一行

  ```java
  @Partial
  @Mock
  DataLoader loader;
  
  @Override
  @Nullable
  public String doSomething() {
      ...
  }
  ```


```
**【错误示例】**

```
##### 场景1：多个注解共处一行
- 错误示例：

  ```java
  @Partial@Mock
  DataLoader loader;
  
  @Nullable@Override
  public String doSomething() {
      ...
  }
  ```


```
**【修复建议】**

推荐使用[HiCode的codecheck插件](https://hicode.huawei.com/#/docs/IDE%E6%8F%92%E4%BB%B6/CodeCheck)的检查和修复功能，或使用开源项目[EasyCode](https://openx.huawei.com/EasyCode/overview)中的代码格式化模板对代码进行格式化处理。
