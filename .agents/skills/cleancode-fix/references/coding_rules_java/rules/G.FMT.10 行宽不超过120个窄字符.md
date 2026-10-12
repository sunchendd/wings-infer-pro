# G.FMT.10 行宽不超过120个窄字符

- **规则ID**：0c52e8b2-0bf7-40c4-8863-d5b5312d99b3
- **更新时间**：2026-04-07 04:00:01

---

**【问题级别】**

提示

**【描述】**

建议代码每行不超过maxLineLength(默认值为120，支持动态配置)个窄字符，保证在屏幕中可以呈现完整代码行，不需要拖动横向滚动条来查看完整代码。



对于宽字符，实际在IDE中的呈现宽度可通过cnCharLength参数进行设置，该参数的默认值值为1（结合IntelliJ IDEA的实际呈现效果约为1.5）。

**【正确示例】**

```
##### 场景1：
- 修复示例：在合适处断行

  ```java
  public void doSomething(HashMap<String, String> hashMap,
      HashSet<String> hashSet, List<String> stringList, String describe) {
         ...
  }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：

  ```java
  public void doSomething(HashMap<String, String> hashMap, HashSet<String> hashSet, List<String> stringList, String describe) {
      // 代码行宽超过120个窄字符
      ...
  }
  ```


```
**【修复建议】**

代码行宽超过maxLineLength个窄字符时，在合理的位置进行换行处理。
