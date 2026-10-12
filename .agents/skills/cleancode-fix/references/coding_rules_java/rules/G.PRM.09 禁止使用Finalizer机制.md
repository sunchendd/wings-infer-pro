# G.PRM.09 禁止使用Finalizer机制

- **规则ID**：239d0f63-d383-4cce-a445-1b59d4704786
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

一般

**【描述】**

finalize()方法的调用时机是不可预测的，常常也是危险的。使用finalize()方法可能会导致不稳定的行为，更差的性能，以及带来移植性问题。

**【正确示例】**

```
##### 场景1：
- 修复示例：

  ```java
  void doSomething() {
      NetworkDemo demo = new NetworkDemo();
      ...     
  }
  ```

```
**【错误示例】**

```
public void test() {
    finalize();
}

```
**【修复建议】**

禁止使用finalize()方法
