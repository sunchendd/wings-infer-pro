# G.TYP.07 避免使用短声明定义一个空的slice

- **规则ID**：3b20bcf6-f4cc-448a-ade8-35ca6023065e
- **更新时间**：2026-04-07 04:20:02

---

**【问题级别】**

一般

**【描述】**

使用`var`关键字时定义空slice更清晰，并且不容易出错。优先使用定义slice类型的nil值，表示一个空的slice。在一些有限的场景（序列化/反序列化），如编码JSON，可使用定义slice类型的nil和[]string{}分别表示JSON的null和array[]。

**【正确示例】**

```
##### 场景1：使用短声明定义一个空的slice
- 修复示例：

  ```go
  func Filter(list []int) []int{
      var filtered []int // 符合：如果可以预估结果的大小时，建议使用make指定容量
      for _, v := range list {
          if v > 10 {
              filtered = append(filtered, v)
          }
      }
      return filtered
  }
  ```


```
**【错误示例】**

```
##### 场景1：使用短声明定义一个空的slice
- 错误示例：

  ```go
  func Filter(list []int) []int{
      filtered := []int{} // 不符合：避免短声明定义一个空的slice
      for _, v := range list {
          if v > 10 {
              filtered = append(filtered, v)
          }
      }
      return filtered
  }
  ```


```
**【修复建议】**

使用`var`关键字时定义空slice
