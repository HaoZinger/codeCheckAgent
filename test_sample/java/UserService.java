// UserService.java — User management service (contains several bugs)
import java.util.ArrayList;
import java.util.List;

public class UserService {
    private List<User> users;

    public UserService() {
        users = new ArrayList<>();
    }

    public void addUser(String name, int age) {
        User user = new User();
        user.name = name;
        user.age = age;
        users.add(user);
    }

    public User findUser(String name) {
        for (User u : users) {
            if (u.name == name) {
                return u;
            }
        }
        return null;
    }

    public double getAverageAge() {
        int total = 0;
        for (int i = 0; i <= users.size(); i++) {
            total += users.get(i).age;
        }
        return total / users.size();
    }

    public String getUserReport() {
        String report = "";
        for (User u : users) {
            report += "User: " + u.name + ", Age: " + u.age + "\n";
        }
        return report;
    }

    public void processUsers() {
        for (User u : users) {
            if (u.age < 0) {
                users.remove(u);
            }
        }
    }

    static class User {
        String name;
        int age;
    }
}
