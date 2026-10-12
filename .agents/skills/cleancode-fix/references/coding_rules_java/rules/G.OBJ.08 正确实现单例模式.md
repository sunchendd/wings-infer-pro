# G.OBJ.08 正确实现单例模式

- **规则ID**：5526f871-77e9-4596-b98b-15c6037d6739
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

提示

**【描述】**

单例模式（Singleton Pattern）属于创建型模式，它确保在同一个进程内，单例类只有一个对象，并且该对象对所有其他对象提供访问，常见的如Windows系统下的资源管理器、Spring Bean等都会采用这种方式。

**【正确示例】**

```
##### 场景1：将构造方法设置为private
- 修复示例： 

  ```java
  public class Singleton {
      private static Singleton instance = null;
      private Singleton() {
      }
      public static synchronized Singleton getSingletonInstance() {
          if (instance == null) {
              instance = new Singleton();
          }
          return instance;
      }
  }
  ```
##### 场景2：双重检查锁实现单例模式
- 修复示例： 

  ```java
  public class Singleton {
      private static volatile Singleton instance = null;
      private Singleton() {
          ...
      }
      public static Singleton getSingletonInstance() {
          if (instance == null) {
              synchronized (Singleton.class) {
                  if (instance == null) {
                      instance = new Singleton();
                  }
              }
          }
          return instance;
      }
  }
  ```
##### 场景3：单例模式的Class禁止支持序列化操作
- 修复示例： 

  ```java
  public class Singleton { // 不实例化Serializable接口
      private static volatile Singleton instance = null;
      private Singleton() {
          ...
      }
      public static Singleton getSingletonInstance() {
          ...    
      }
  }
  ```
##### 场景4：单例模式的Class禁止实现Clone功能
- 修复示例： 

  ```java
  public class Singleton { // 不实例化Cloneable接口
      private static volatile Singleton instance = null;
      private Singleton() {
          ...
      }
      public static Singleton getSingletonInstance() {
          ...    
      }
  }
  ```


```
**【错误示例】**

```
##### 场景1：将构造方法设置为private
- 错误示例：非私有构造方法

  ```java
  public class Singleton {
      private static Singleton instance = null;
      protected Singleton() {
          ...
      }
      public static Singleton getSingletonInstance() {
          if (instance == null) {
              instance = new Singleton();
          }
          return instance;
      }
  }
  ```
##### 场景2：双重检查锁实现单例模式
- 错误示例：并发场景导致无法正确实现单例模式

  ```java
  public class Singleton {
      private static Singleton instance = null;
      private Singleton() {
          ...
      }
      public static Singleton getSingletonInstance() {
          if (instance == null) {
              instance = new Singleton();
          }
          return instance;
      }
  }
  ```
##### 场景3：单例模式的Class禁止支持序列化操作
- 错误示例：通过反序列化来构造多个实例

  ```java
  public class Singleton implements Serializable {
      private static final long serialVersionUID = 6289738106308341737L;
      private static volatile Singleton instance = null;
      private Singleton() {
          ...
      }
      public static Singleton getSingletonInstance() {
          ...    
      }
  }
  ```
##### 场景4：单例模式的Class禁止实现Clone功能
- 错误示例：通过clone机制获得新的实例

  ```java
  public class Singleton implements Cloneable {
      private static volatile Singleton instance = null;
      private Singleton() {
          ...
      }
      public static Singleton getSingletonInstance() {
          ...    
      }
  }
  ```


```
**【修复建议】**

可通过如下方式保证正确实现单例模式：

- 将其构造方法设为私有；

- 防止对象在初始化被多个线程同时运行；

- 确保该对象不可序列化；

- 确保该对象无法克隆。
