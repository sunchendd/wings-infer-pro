# G.PRM.01 将集合转为数组时使用Collection<T>.toArray(T[])方法；Java 11后使用Collection<T>.toArray(IntFunction<T[]>)

- **规则ID**：e5607f7e-d041-4cc0-a8fc-8459542f4328
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

对于将集合转为数组操作，Java 11引入了`Collection<T>.toArray(IntFunction<T[]> generator)`，它更好的原因是不需要创建临时数组，一方面节省空间，另一方面这样就不用去考虑`toArray(T[])`里的参数长度对方法行为以及结果的影响。



另外，java.util.stream中各Stream的`toArray()`、`toArray(IntFunction<A[]>)`也是常用的。



Java 11前`toArray(T[] a)`的参数应采用**零长度的数组**，这样可保证有更好的性能。数组容量大小产生的影响如下：



- 等于0，动态创建与size相同的数组，性能最好；

- 大于0但小于size，重新创建大小等于size的数组，增加GC负担；

- 等于size，在高并发情况下，数组创建完成之后，size正在变大的情况下，负面影响与上相同；

- 大于size，空间浪费，且在size处插入null值，存在NullPointerException隐患。

**【正确示例】**

```
##### 场景1：集合转数组操作
- 修复示例1：

  ```java
  List<String> list = new ArrayList<>(DEFAULT_CAPACITY);
  list.add(getElm());
  ...
  String[] array = list.toArray(new String[0]);
  ```
- 修复示例2：Java11+

  ```java
  List<String> list = new ArrayList<>(DEFAULT_CAPACITY);
  list.add(getElm());
  ...
  String[] array = list.toArray(String[]::new);
  ```


```
**【错误示例】**

```
##### 场景1：集合转数组操作
- 错误示例：

  ```java
  List<String> list = new ArrayList<>(DEFAULT_CAPACITY);
  list.add(getElm());
  ...
  String[] array = list.toArray(new String[DEFAULT_CAPACITY + 1]);
  ```


```
**【修复建议】**

将集合转为数组时推荐使用`Collection<T>.toArray(T[])`方法，参数应采用**零长度的数组**；Java 11后使用`Collection<T>.toArray(IntFunction<T[]>)`
