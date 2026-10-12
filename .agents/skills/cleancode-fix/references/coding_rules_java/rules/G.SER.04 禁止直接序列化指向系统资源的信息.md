# G.SER.04 禁止直接序列化指向系统资源的信息

- **规则ID**：66c9bb45-db0e-4db7-8d99-09b8e68f1450
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

严重

**【描述】**

当序列化结果中含有指向系统的资源时，这些信息很容易被篡改。当恶意用户篡改了指向系统的资源时，反序列化的对象会直接操作这些被攻击者指定的系统资源，导致任意文件读取或修改。

**【正确示例】**

```
##### 场景1： 类成员变量为File，且被序列化
- 修复示例1：用transient修饰类成员变量File

  ```java
  final class SomeResource implements Serializable {
      private static final long serialVersionUID = 6562477636399915529L;

      private transient File file;

      public SomeResource(String fileName) {
          file = new File(fileName);
          ...
      }
  }
  ```


```
**【错误示例】**

```
##### 场景1： 类成员变量为File，且被序列化
- 错误示例：

  ```java
  final class SomeResource implements Serializable {
      private static final long serialVersionUID = -2589766491699675794L;

      private File file;

      public SomeResource(String fileName) {
          file = new File(fileName);
          ...
      }
  }
  ```


```
**【修复建议】**

禁止直接序列化指向系统资源的信息，如实现Serializable的类，其成员变量为File或FileDescriptor时，用transient修饰，避免这些对象被序列化。
