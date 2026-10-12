# G.TYP.13 在引用类型向下转换前用instanceof进行判断

- **规则ID**：07fec15f-062f-47d0-bbea-deb9e96828bd
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

一般

**【描述】**

没有判断类型直接进行类型转换，可能会因类型不匹配而导致运行时异常`java.lang.ClassCastException`。简单的修改方法是在强制转换之前使用`instanceof`进行判断，确认转换操作的可行性，除此之外其他的类型检查方式也是可行的（如直接判断Class类型），只要能保证类型可正确转换即可。



当集合或数组中保存多种类型的对象，当遍历这些数据使用时可以使用instanceof对每个元素的类型进行判断。但是运行时类型检查是一项耗时的操作，另外还可能带来修改点过多、工作量巨大的问题，同时维护的工作量也会倍增。最佳实现方式是改善设计，使集合/数组中只有同一种类型的对象。

**【正确示例】**

```
##### 场景1：类型强转前，未判断类型是否兼容，当类型不匹配时会抛出`java.lang.ClassCastException`
- 修复示例1：

  ```java
  public void doSomething(Object obj) {
      ...
      if(obj instanceof SomeResource) {
          SomeResource resouce = (SomeResource)obj;
          ...
      }
  }
  ```


```
**【错误示例】**

```
##### 场景1：类型强转前，未判断类型是否兼容，当类型不匹配时会抛出`java.lang.ClassCastException`
- 错误示例：

  ```java
  public void doSomething(Object obj) {
      ...
      SomeResource resouce = (SomeResource)obj;
      ...
  }
  ```


```
**【修复建议】**

引用类型向下转换前用`instanceof`进行判断；除此之外其他的类型检查方式也是可行的（如直接判断Class类型），只要能保证类型可正确转换即可。
