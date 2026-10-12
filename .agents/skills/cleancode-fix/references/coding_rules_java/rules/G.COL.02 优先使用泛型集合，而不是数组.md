# G.COL.02 优先使用泛型集合，而不是数组

- **规则ID**：286724de-92ee-4756-96fd-36b37085ebce
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

泛型是不可变的，数组是协变的。当向数组中添加类型不匹配的元素时，在运行期才会发生错误，而对于集合，在编译期就会报错。另外，由于类型不安全无法创建泛型数组。



泛型与数组不能很好地混合使用，如果需要使用一个“泛型化的数组”，更好地选择是使用集合。

**【正确示例】**

```
##### 场景1：
- 修复示例： 


  ```java
    private final List<T> lists; // 泛型列表
    private final List<String> longs; // 具体化的列表

    List<Object> objectList = new ArrayList<String>(DEFAULT_CAPACITY); // 不兼容类型，编译报错
    objectList.add("test value");
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：

  ```java
    private final T[] someArray; // 泛型数组，不建议
    private final Object[] objArray; // 协变化的数组声明，不建议

    Object[] objectArray = new Integer[10]; // 协变化的数组初始化，不建议
    objectArray[0] = "test value"; // 运行时抛出ArrayStoreException
  ```


```
**【修复建议】**

相对于数组，推荐优先使用泛型集合。
