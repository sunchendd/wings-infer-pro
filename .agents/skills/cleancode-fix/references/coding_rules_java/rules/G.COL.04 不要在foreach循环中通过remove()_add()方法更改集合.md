# G.COL.04 不要在foreach循环中通过remove()/add()方法更改集合

- **规则ID**：521250f1-316c-47f4-b984-72c61e553661
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

严重

**【描述】**

java.util.concurrent包之外的（非concurrent）集合在foreach循环中不要更改，否则可能会导致ConcurrentModificationException。当需要遍历集合并删除部分元素时，可采用removeIf()方法或Iterator的remove()方法。个别集合（例如CopyOnWriteArrayList）的Iterator中remove()方法会抛出UnsupportedOperationException。

**【正确示例】**

```
##### 场景1：
- 修复示例： 


  ```java
  // 使用Java 8 Collection中的removeIf方法
  list.removeIf(item -> shouldDelete(item));
  
  // 使用Iterator删除元素
  Iterator<String> iterator = list.iterator();
  while (iterator.hasNext()) {
      String item = iterator.next();
      if (shouldDelete(item)) {
          iterator.remove();
      }
  }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：

  ```java
  for (String item : list) {
      if (shouldDelete(item)) {
          list.remove(item);
      }
  }
  ```


```
**【修复建议】**

在遍历集合中的元素时，如果需要对集合进行更改，应该使用迭代器。
