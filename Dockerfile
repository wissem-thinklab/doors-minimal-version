FROM nginx:alpine

# Copy all files to nginx html directory
COPY . /usr/share/nginx/html/

# Copy custom nginx config if you have one (optional)
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]