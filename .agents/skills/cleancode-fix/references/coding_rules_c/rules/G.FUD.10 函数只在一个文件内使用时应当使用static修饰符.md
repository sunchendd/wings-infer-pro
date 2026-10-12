# G.FUD.10 函数只在一个文件内使用时应当使用static修饰符

- **规则ID**：5df90688-ca6f-4902-897b-4c03e7dbd922
- **更新时间**：2026-04-07 04:10:03

---

**【问题级别】**

一般

**【描述】**

函数如果只在一个文件内使用，应当使用static修饰符。



如果函数声明的范围比需要的范围大，可能被意外引用而产生预期之外的错误。

**【正确示例】**

```
##### 场景1：只在一个.c文件中使用的函数，没有加static修饰符。
- 修复示例：

  ```c
  static int Foo(int value) // 符合：Foo只在当前文件使用，增加static修饰符
  {
      ...
  }
  int Goo(int value)
  {
      int result = Foo(value);
      ...
  }
  ```

```
**【错误示例】**

```
##### 场景1：只在一个.c文件中使用的函数，没有加static修饰符。
- 错误示例：

  ```c
  int Foo(int value) // 不符合：Foo只在当前文件使用，没有加static修饰符
  {
      ...
  }
  int Goo(int value)
  {
      int result = Foo(value);
      ...
  }
  ```

```
**【修复建议】**

函数只在一个文件内使用时，添加static修饰符。

推荐使用[Huawei CodeCheck插件](https://3ms.huawei.com/km/groups/3946724/blogs/details/15159305?l=zh-cn)的自动修复/一键格式化功能，详细使用说明见。
