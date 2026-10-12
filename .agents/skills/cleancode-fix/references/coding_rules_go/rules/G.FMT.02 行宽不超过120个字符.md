# G.FMT.02 行宽不超过120个字符

- **规则ID**：0977db16-ea64-4669-8a86-1d34acfa7174
- **更新时间**：2026-04-07 04:20:01

---

**【问题级别】**

提示

**【描述】**

代码行宽不宜过长，不可以超过120个字符。

**【正确示例】**

```
##### 场景1：超长函数签名未断行
- 修复示例1：在适当处断行

  ```go
  // 符合：行宽不超过120个字符
  func testCode121Characters(TAddressStringFor40Digits int, TAddressStringFor40Digits1 int,
      TAddressStrigits2 int, i int) {
      // Code
  }
  ```


```
**【错误示例】**

```
##### 场景1：超长函数签名未断行
- 错误示例：

  ```go
  // 不符合：行宽超过120个字符
  func testCode121Characters(TAddressStringFor40Digits int, TAddressStringFor40Digits1 int, TAddressStrigits2 int, i int) {
      // Code
  }
  ```


```
**【修复建议】**

行宽超过120个字符要进行换行。



较长的语句、表达式或参数要分成多行书写，长表达式要在低优先级操作符处划分新行，操作符放在行尾，划分出的新行要进行适当的缩进，使排版整齐，语句可读。
