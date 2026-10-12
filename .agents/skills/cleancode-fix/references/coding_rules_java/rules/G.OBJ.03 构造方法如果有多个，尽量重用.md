# G.OBJ.03 构造方法如果有多个，尽量重用

- **规则ID**：80b92136-f9a2-433e-9dad-951242c07cf5
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

一般

**【描述】**

由于可选参数导致的存在多个构造方法时，参数少的构造方法可以重用参数更多的构造方法，这样可以是代码更加简洁。

**【正确示例】**

```
##### 场景1：
- 修复示例：复用参数更多的构造方法

  ```java
    public class Student {
        private String name;
        private String sex;
        private int weight; // 可选参数
        private int height; // 可选参数
        private int age;    // 可选参数
        public Student(String name, String sex) {
            this(name, sex, 0);
        }
        public Student(String name, String sex, int weight) {
            this(name, sex, weight, 0);
        }
        public Student(String name, String sex, int weight, int height) {
            this(name, sex, weight, height, 0);
        }
        public Student(String name, String sex, int weight, int height, int age) {
            this.name = name;
            this.sex = sex;
            this.weight = weight;
            this.height = height;
            this.age = age;
        }
        ...
    }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例： 

  ```java
    public class Student {
        private String name;
        private String sex;
        private int weight; // 可选参数
        private int height; // 可选参数
        private int age;    // 可选参数
        public Student(String name, String sex) {
            this.name = name;
            this.sex = sex;
        }
        public Student(String name, String sex, int weight) {
            this.name = name;
            this.sex = sex;
            this.weight = weight;
        }
        public Student(String name, String sex, int weight, int height) {
            this.name = name;
            this.sex = sex;
            this.weight = weight;
            this.height = height;
        }
        public Student(String name, String sex, int weight, int height, int age) {
            this.name = name;
            this.sex = sex;
            this.weight = weight;
            this.height = height;
            this.age = age;
        }
        ...
    }
  ```


```
**【修复建议】**

由于可选参数导致的存在多个构造方法时，参数少的构造方法重用参数更多的构造方法。
