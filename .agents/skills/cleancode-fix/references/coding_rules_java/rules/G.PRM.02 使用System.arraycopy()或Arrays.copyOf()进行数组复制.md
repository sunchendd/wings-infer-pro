# G.PRM.02 使用System.arraycopy()或Arrays.copyOf()进行数组复制

- **规则ID**：3e7640fe-9b01-4675-aa83-2e288c83e87d
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

在将一个数组对象复制成另外一个数组对象时，不要自己使用循环复制，可以使用Java提供的`System.arraycopy()`功能来复制数据对象，这样做可以避免出错，而且效率会更高。`java.util.Arrays.copyOf()`是对`System.arraycopy()`便利化封装。数组复制有如下特性：



- 对于一维数组，且数组元素为基本类型或String类型时，数组复制属于深复制，即复制后的数组与原始数组的元素互不影响；

- 对于多维数组，或一维数组中的元素是引用类型时，数组复制属于浅复制，即复制后的数组与原始数组的元素引用指向的是同一个对象。

**【正确示例】**

```
##### 场景1： 使用for循环进行数组复制
- 修复示例1：使用`System.arraycopy()`进行数组复制

  ```java
  int[] src = {1, 2, 3, 4, 5};
  int[] dest = new int[5];
  System.arraycopy(src, 0, dest, 0, 5);
  ```


```
**【错误示例】**

```
##### 场景1： 使用for循环进行数组复制
- 错误示例：

  ```java
  int[] src = {1, 2, 3, 4, 5};
  int[] dest = new int[5];
  for (int i = 0; i < 5; i++) {
      dest[i] = src[i];
  }
  ```


```
**【修复建议】**

使用`System.arraycopy()`或`Arrays.copyOf()`进行数组复制。
