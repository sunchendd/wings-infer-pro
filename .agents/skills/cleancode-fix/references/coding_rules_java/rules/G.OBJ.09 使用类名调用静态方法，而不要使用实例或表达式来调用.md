# G.OBJ.09 使用类名调用静态方法，而不要使用实例或表达式来调用

- **规则ID**：373f084e-85dd-4697-9a70-22b5235f8696
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

严重

**【描述】**

明确地使用类名调用静态方法不容易造成混淆。使用实例调用静态方法时，调用的静态方法是声明类型的静态方法，与实例的实际类型无关，可能会导致与预期的结果不一致。当父类和子类有同名静态方法时，声明父类变量引用子类实例，使用该实例调用同名的静态方法调用的是父类的静态方法，而非子类的静态方法。类的静态属性也要使用类名进行调用。

**【正确示例】**

```
##### 场景1：使用类名调用静态方法
- 修复示例： 用类名来调用静态方法

```java
class Dog {
    public static void bark() {
        System.out.print("woof");
    }
}

class Basenji extends Dog {
    public static void bark() {
        System.out.println("miao");
    }
}

public class Bark {
    public static void main(String[]  args) {
        Dog.bark();
        Basenji.bark();
    }
}
```


```
**【错误示例】**

```
##### 场景1：使用类名调用静态方法
- 错误示例： 上述示例中，对bark()的两次调用，实际调用的都是Dog.bark()方法。

```java
class Dog {
    public static void bark() {
        System.out.println("woof");
    }
}

class Basenji extends Dog {
    public static void bark() {
        System.out.println("miao");
    }
}

 public class Bark {
    public static void main(String[]  args) {
        Dog woofer = new Dog();
        Dog nipper = new Basenji();
        woofer.bark();
        nipper.bark();
    }
}
```


```
**【修复建议】**

使用类名来调用静态方法或静态变量。
