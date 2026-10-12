# G.SER.01 尽量避免实现Serializable接口

- **规则ID**：52e6778f-20ab-4864-b0e5-bb8a474b7382
- **更新时间**：2026-04-07 04:00:03

---

**【问题级别】**

提示

**【描述】**

对于支持序列化操作的类，其实例属性如果不支持序列化操作，在对该类进行序列化操作时会出异常。class中的静态属性、transient修饰的非静态属性不会进行序列化操作。

**【正确示例】**

```
##### 场景1：
- 修复示例1：使用transient修饰属性
  ```java
  public class AvoidSerialization implements Serializable {
   
     public transient AttributeClass attribute= new AttributeClass ();
     ...
  }

   class AttributeClass{
   ...
   }
  ```
- 修复示例2：使用static修饰属性
  ```java
  public class AvoidSerialization implements Serializable {
   
     public static AttributeClass attribute= new AttributeClass ();
     ...
  }

   class AttributeClass{
   ...
   }
  ```
- 修复示例3：属性类实例化Serializable 
  ```java
  public class AvoidSerialization implements Serializable {
   
     public static AttributeClass attribute= new AttributeClass ();
     ...
  }

   class AttributeClass implements Serializable{
   ...
   }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：支持序列化操作的类的属性不支持序列化操作

  ```java
  public class AvoidSerialization implements Serializable {
   
     public AttributeClass attribute= new AttributeClass ();
     ...
  }

   class AttributeClass{
  
   }
  ```


```
**【修复建议】**

对于支持序列化操作的类，其实例属性需支持序列化操作，不需要进行序列化操作的属性可以设置为transient。
